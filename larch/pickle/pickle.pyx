#cython: boundscheck=False, always_allow_keywords=False, language_level=3, profile=False
"""

Difference to python pickle:
----------------------------

- no memo attribute
- no clear_memo()
- no persistent_id interface
- pickle3 can only load utf8 encoded pickle2 strings


Differences to msg pack protocol:
--------------------------------

ext type LIST:
   the size field is interpreted as item count

ext type VERSION:
   the size field is interpreted as version number

ext type OBJECT:
   after the extension byte the object state is saved

0xc1:
   this opcode is interpreted as REF Field
   +------+------+------+------+------+
   | 0xcf |XXXXXX|xxxxxx|xxxxxx|xxxxxx|
   +------+------+------+------+------+
   XXXX 32bit big-endian ref id


Python 2 <-> Python 3 Pickle
----------------------------

Python 2 pickles strings(bytes) to msg-pack str type and unicode to
the extension type UNISTR

Python 3 pickles strings(unicode) to msg-pack str type and bytes to
msg-pack byte type

CHANGES TO Protocol 4
Type OBJECT_NEW_CUSTOM is abandoned
Type FAST_NEW is introduced and a slighly smaller footprint und loads faster
"""
import sys
import types
import cython
import builtins
import operator
import logging
from libc.string cimport memcpy
from libcpp cimport bool
from cpython.bytes cimport (
    PyBytes_FromStringAndSize, PyBytes_GET_SIZE, _PyBytes_Resize)
from cpython.long cimport PyLong_AsLong
from cpython.tuple cimport PyTuple_GET_SIZE, PyTuple_Check, PyTuple_GET_ITEM
from cpython.dict cimport PyObject, PyDict_GetItem, PyDict_CheckExact, PyDict_Update
from cpython.unicode cimport (
    PyUnicode_CheckExact, PyUnicode_FromObject, PyUnicode_Decode)
from cpython.ref cimport Py_DECREF, Py_INCREF, Py_CLEAR, PyTypeObject
from cpython.exc cimport PyErr_Clear, PyErr_SetString, PyErr_Restore
from . import register as pickle_register


cdef set secure_objects = pickle_register.secure_objects
cdef set secure_modules = pickle_register.secure_modules

logger = logging.getLogger("larch.pickle")


IF PY_MAJOR_VERSION > 2:
    import copyreg
    import _compat_pickle

    cdef:
        dict name_mapping_2to3 = _compat_pickle.NAME_MAPPING
        dict import_mapping_2to3 = _compat_pickle.IMPORT_MAPPING
        dict name_mapping_3to2 = _compat_pickle.REVERSE_NAME_MAPPING
        dict import_mapping_3to2 = _compat_pickle.REVERSE_IMPORT_MAPPING
ELSE:
    import copy_reg as copyreg

cdef object REDUCE_PROTOCOL = 4
cdef MAX_PROTOCOL_VERSION = 4


cdef extern from "structmember.h":
    ctypedef struct PyLongObject
    ctypedef char uchar_t "unsigned char"
    size_t _PyLong_NumBits(object o)
    int _PyLong_AsByteArray(
        PyLongObject* o, uchar_t* bytes, size_t n,
        int little_endian, int is_signed)
    int _PyLong_Sign(object o)
    object _PyLong_FromByteArray(
	uchar_t* bytes, size_t n,
	int little_endian, int is_signed)

cdef extern from "Python.h":
    char* Bytes_AS_STRING "PyBytes_AS_STRING"(object string)
    PyObject* Object_GetAttrString "PyObject_GetAttrString"(object o, char *attr_name)

cdef extern from "pickle.hpp":
    ctypedef unsigned int   uint32_t
    ctypedef unsigned char  uint8_t

    ctypedef int (*write_t)(object pickler, void* data, size_t size) except -1
    ctypedef int (*read_t)(object unpickler, void* data, size_t size) except -1

    ctypedef void (*debug_t)(char* msg, object o, long v)
    cdef debug_t debug

    void throw_python_error()

    ctypedef object (*tp_new_t)(PyTypeObject*, object, PyObject*)
    cdef tp_new_t GET_NEW(object)

    cdef enum EXT_TYPES:
        VERSION, LONG, REF, LIST, OBJECT, OBJECT_NEW, GLOBAL, SINGLETON,
        OLD_STYLE, INIT_ARGS, END_OBJECT_ITEMS, BYTES, UNISTR,
        OBJECT_NEW_CUSTOM, GLOBAL_OBJECT, FAST_NEW, COUNT_EXT_TYPES


IF True:
    cdef show_debug(char* msg, object o, long v):
        if <PyObject*>o is NULL:
            print(msg, hex(v), "NULL")
        else:
            print(msg, hex(v), repr(o), hex(<size_t><PyObject*>o), (<PyObject*>o).ob_refcnt)

    debug = <debug_t>show_debug


cdef extern from "pack.hpp":
    ctypedef void (*pack_t)(Packer* p, object o)

    cdef cppclass StringWriter:
        void reset()
        int write(void* data, size_t size)
        object result()

    cdef cppclass TypeMap:
        void register_type(object key, pack_t saver)

    cdef TypeMap pickle_registry
    cdef pack_t save_object_ptr
    cdef pack_t save_string_ptr
    cdef void *string_type

    cdef cppclass Packer:
        PyObject*  pickler
        write_t do_write
        int protocol
        size_t min_string_size_for_ref;

        Packer(object pickler, int protocol, bool with_refs)

        bool save_ref(object o)
        void dump(object o)
        int first_dump(object o) except -1

        uint32_t reset()
        void pack_version(uint8_t version) except +
        void pack_nil()
        bool pack8(uint8_t value)
        int pack_int(long value)
        int pack_ext(uint8_t typecode, size_t l)
        int pack_bool(bool value)
        int pack_double(double d)
        int pack_bin(size_t l)
        int pack_str(size_t l)
        int pack_array(size_t n)
        int pack_map(size_t n)
        void write(void* value, size_t size)
        void write_int(uint32_t value)

    void save_none(Packer* p, object o)
    void save_bool(Packer* p, object o)
    void save_int(Packer* p, object o)
    void save_float(Packer* p, object o)
    void save_tuple(Packer* p, object o)
    void save_list(Packer* p, object o)
    void save_dict(Packer* p, object o)
    void save_bytes(Packer* p, object o)
    void save_unicode(Packer* p, object o)
    void save_str2(Packer* p, object o)
    void save_str3(Packer* p, object o)


cdef extern from "unpack.hpp":
    ctypedef PyObject* (*unpack_t)(
        Unpacker* p, uint8_t code, size_t size)

    cdef unpack_t unpickle_registry[]

    cdef cppclass StringReader:
        char* data
        size_t pos, size
        void read(void* bufer, size_t size)

    cdef cppclass Unpacker:
        PyObject *unpickler
        read_t do_read
        size_t min_string_size_for_ref

        Unpacker(object unpickler)
        uint32_t reset()
        PyObject* load()

        object load_object"load"()
        object first_load()

        PyObject* get_stamped_ref(uint32_t ref)
        uint32_t get_stamp()
        void stamp(uint32_t ref, object o)
        void change_stamp(uint32_t ref, object o)
        int read(char* data, size_t size)
        void read32(uint32_t* value)
        void read8(uint8_t* value)

    PyObject* load_uint4(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_int4(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_uint8(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_int8(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_uint16(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_int16(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_uint32(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_int32(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_uint64(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_int64(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_nil(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_false(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_true(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_array4(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_array16(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_array32(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_float(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_long(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_extf(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_ext8(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_ext16(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_ext32(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_list(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_map4(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_map16(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_map32(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_bin8(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_bin16(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_bin32(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_str4(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_str8(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_str16(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_str32(Unpacker *p, uint8_t code, size_t size)
    PyObject* load_bytes(Unpacker* p, uint8_t code, size_t size)
    PyObject* load_unicode(Unpacker* p, uint8_t code, size_t size)

cdef:
    dict dispatch_table = copyreg.dispatch_table
    dict extension_registry = copyreg._extension_registry
    dict inverted_registry = copyreg._inverted_registry
    dict extension_cache = copyreg._extension_cache
    dict modules = sys.modules
    _end_item = object()


cdef class Pickler
cdef class Unpickler


ctypedef int (*write_file_t)(object file, void *data, size_t size)
"""writes data to file"""

ctypedef int (*read_file_t)(object file, void *data, size_t size)
"""reads data from file"""


# File Handlers
# ------------------------------


# String Buffer
@cython.auto_pickle(False)
cdef class OutputBuffer:
    cdef StringWriter *writer

    def __init__(self):
        self.writer = new StringWriter()

    def __dealloc__(self):
        del self.writer

    cdef void reset(self):
        self.writer.reset()

    cdef bytes result(self):
        return self.writer.result()


cdef int write_buffer(object pickler, void* data, size_t size) except -1:
    return (<OutputBuffer>(<Pickler>pickler).file).writer.write(data, size)


@cython.auto_pickle(False)
cdef class _BufferContainer:
    cdef StringReader sreader

    cdef _BufferContainer set(self, bytes buffer):
        self.sreader.data = buffer
        self.sreader.pos = 0
        self.sreader.size = len(buffer)
        return self


cdef int read_buffer(object unpickler, void* buffer, size_t size) except -1:
    (<_BufferContainer>(<Unpickler>unpickler).file).sreader.read(buffer, size)


# Python Filelike
@cython.auto_pickle(False)
cdef class _FileLike:
    cdef:
        object write
        object read

    def __init__(self, file_like):
        self.write = file_like.write
        self.read = file_like.read


cdef int write_file(object pickler, void* data, size_t size) except -1:
    (<_FileLike>(<Pickler>pickler).file).write((<char*>data)[:size])
    return 1


cdef int read_file(object unpickler, void* data, size_t size) except -1:
    cdef:
        _FileLike f = (<Unpickler>unpickler).file
        bytes b = f.read(size)
        size_t rsize = PyBytes_GET_SIZE(b)

    if rsize != size:
        raise EOFError()

    memcpy(data, Bytes_AS_STRING(b), rsize)
    return 1

# External (cython) filelike
@cython.auto_pickle(False)
cdef class ExternFileLike:
    cdef:
        object file
        write_file_t write
        read_file_t read

cdef int write_external(object pickler, void* data, size_t size) except -1:
    cdef ExternFileLike ef = <ExternFileLike>(<Pickler>pickler).file
    return ef.write(ef.file, data, size)


cdef int read_external(object unpickler, void* data, size_t size) except -1:
    cdef ExternFileLike ef = <ExternFileLike>(<Unpickler>unpickler).file
    return ef.read(ef.file, data, size)


@pickle_register.secure_unpickle
class PickleError(Exception):
    pass


@pickle_register.secure_unpickle
class PicklingError(PickleError):
    pass


@pickle_register.secure_unpickle
class UnpicklingError(PickleError):
    pass


@pickle_register.secure_unpickle
class SecurityError(UnpicklingError):
    pass


# Pickler Functions
# ----------------------------------

cdef inline void reraise():
    type_, exc, traceback = sys.exc_info()
    PyErr_Restore(<PyObject*>type_, <PyObject*>exc, <PyObject*>traceback)
    throw_python_error()


cdef void save_long(Packer* p, object o):
    # see original _pickle.c
    cdef:
        size_t nbytes, nbits = _PyLong_NumBits(o)
        int sign = _PyLong_Sign(o)
        bytes tmp
        char* data
        long v

    try:
        v = PyLong_AsLong(o)
    except:
        pass
    else:
        p.pack_int(v)
        return

    if p.save_ref(o): return

    nbytes = (nbits >> 3) + 1
    if nbytes > 0x7fffffffL:
        PyErr_SetString(OverflowError, "long too large to pickle")
        throw_python_error()

    tmp = PyBytes_FromStringAndSize(NULL, nbytes)
    data = Bytes_AS_STRING(tmp)

    if _PyLong_AsByteArray(<PyLongObject*>o, <uchar_t*>data, nbytes, 1, 1) < 0:
        throw_python_error()

    if (sign < 0 and nbytes > 1
        and data[nbytes-1] == 0xff and (data[nbytes-2] & 0x80) != 0):
        nbytes -= 1

    p.pack_ext(LONG, nbytes)
    p.write(<char*>data, nbytes)


cdef inline int _save_global(Packer* p, object o) except -1:
    (<Pickler>p.pickler).pack_import1(GLOBAL, o)


cdef void save_global(Packer* p, object o):
    try:
        _save_global(p, o)
    except:
        reraise()


cdef pack_state_array(Packer *p, tuple state):
    cdef PyObject* tmp
    tmp = PyTuple_GET_ITEM(state, 3)
    if <object>tmp is not None:
        for i in <object>tmp:
            p.dump(i)


cdef pack_state_dict(Packer *p, tuple state):
    cdef PyObject* tmp
    tmp = PyTuple_GET_ITEM(state, 4)
    if <object>tmp is not None:
        for k, v in <object>tmp:
            p.dump(k)
            p.dump(v)


cdef void save_object_state(Packer* p, tuple state):
    cdef:
        size_t size
        PyObject* tmp

    size = PyTuple_GET_SIZE(state)
    if size > 2:
        tmp = PyTuple_GET_ITEM(state, 2)
        p.dump(<object>tmp)
    else:
        p.pack_nil()

    if size > 3:
        pack_state_array(p, state)
    p.pack_ext(END_OBJECT_ITEMS, 1)

    if size > 4:
        pack_state_dict(p, state)
    p.pack_ext(END_OBJECT_ITEMS, 1)

    if size > 5:
        raise PicklingError(
            "Cannot pickle object with more then 5 reduce items")


cdef inline int _save_reduced(Packer* p, object o) except -1:
    if p.save_ref(o): return 0
    state = o.__reduce_ex__(REDUCE_PROTOCOL)
    if isinstance(state, basestring):
        (<Pickler>p.pickler).pack_import2(SINGLETON, o.__module__, state)
        return 0

    p.pack_ext(OBJECT, 1)
    p.dump(<object>PyTuple_GET_ITEM(state, 0))
    p.dump(<object>PyTuple_GET_ITEM(state, 1))
    save_object_state(p, state)


cdef void save_reduced(Packer* p, object o):
    try:
        _save_reduced(p,  o)
    except:
        reraise()


cdef inline int _save_new_object(Packer* p, o) except -1:
    if p.save_ref(o): return 0
    state = o.__reduce_ex__(REDUCE_PROTOCOL)
    if isinstance(state, basestring):
        (<Pickler>p.pickler).pack_import2(SINGLETON, o.__module__, state)
        return 0

    return _save_new_object_finish(p, o, state)

cdef inline int _save_new_object_finish(Packer* p, o, state) except -1:
    p.pack_ext(OBJECT_NEW, 1)
    p.dump(<object>PyTuple_GET_ITEM(state, 1))
    save_object_state(p, state)
    return 0


cdef inline void save_new_object(Packer* p, object o):
    try:
        if p.protocol < 4:
            _save_new_object(p, o)
        else:
            _fast_save(p, o)
    except:
        reraise()


cdef inline int _fast_save(Packer* p, object o) except -1:
    if p.save_ref(o): return 0
    state = o.__reduce_ex__(REDUCE_PROTOCOL)
    if isinstance(state, basestring):
        (<Pickler>p.pickler).pack_import2(SINGLETON, o.__module__, state)
        return 0

    return _fast_save_finish(p, o, state)


cdef inline int _fast_save_finish(Packer* p, o, state) except -1:
    cdef:
        size_t size
        size_t i

    size = PyTuple_GET_SIZE(state)
    i = size - 1
    while i > 1:
        if <object>PyTuple_GET_ITEM(state, i) is None:
            size -= 1
            i -= 1
        else:
            break
    p.pack_ext(FAST_NEW, size)
    p.dump(<object>PyTuple_GET_ITEM(state, 1))
    if size > 2:
        p.dump(<object>PyTuple_GET_ITEM(state, 2))
        if size > 3:
            pack_state_array(p, state)
            p.pack_ext(END_OBJECT_ITEMS, 1)
            if size > 4:
                pack_state_dict(p, state)
                p.pack_ext(END_OBJECT_ITEMS, 1)
                if size > 5:
                    raise PicklingError(
                        "Cannot pickle object with more then 5 reduce items")


cdef int _save__newobj__(Packer* p, object o, state) except -1:
    register_type(o, save_new_object)
    if p.protocol < 4:
        return _save_new_object_finish(p, o, state)
    else:
        return _fast_save_finish(p, o, state)


cdef inline int _save_object(Packer* p, object o) except -1:
    cdef:
        PyObject *reduce_func
        pack_t next_save_func = NULL

    if p.save_ref(o) > 0:
        return 0

    reduce_func = PyDict_GetItem((<Pickler>p.pickler).dispatch_table, type(o))
    if reduce_func is NULL:
        do_reduce = o.__reduce_ex__
        try:
            state = do_reduce(REDUCE_PROTOCOL)
        except TypeError:
            # a meta class
            try:
                (<Pickler>p.pickler).pack_import1(GLOBAL_OBJECT, o)
            except:
                reraise()
            return 0
        else:
            if not isinstance(state, basestring):
                next_save_func = save_reduced
    else:
        state = (<object>reduce_func)(o)

    if isinstance(state, basestring):
        (<Pickler>p.pickler).pack_import2(SINGLETON, o.__module__, state)
        return 0

    if ((<object>PyTuple_GET_ITEM(state, 0)).__name__) == "__newobj__":
        return _save__newobj__(p, o, state)
    else:
        p.pack_ext(OBJECT, 1)
        p.dump(<object>PyTuple_GET_ITEM(state, 0))
        p.dump(<object>PyTuple_GET_ITEM(state, 1))

    if next_save_func:
        register_type(o, next_save_func)

    save_object_state(p, state)


cdef void save_object(Packer* p, object o):
    try:
        _save_object(p, o)
    except:
        reraise()

save_object_ptr = save_object


cdef void save_impossible(Packer* p, object o):
    IF PY_MAJOR_VERSION > 2:
        cdef:
            unicode msg = "Cannot save {!r}".format(o)
            bytes bmsg = msg.encode()
    ELSE:
        cdef:
            bytes bmsg = "Cannot save {!r}".format(o)

    PyErr_SetString(PicklingError, bmsg)
    throw_python_error()


cdef void register_type(o, pack_t saver):
    pickle_registry.register_type(type(o), saver)


register_type(1, save_int)
register_type(1L, save_long)
register_type(True, save_bool)
register_type(None, save_none)
register_type(1.0, save_float)
register_type((), save_tuple)
register_type([], save_list)
register_type({}, save_dict)
register_type(type, save_global)
register_type(iter([]), save_impossible)
register_type(iter(()), save_impossible)
pickle_registry.register_type(types.GeneratorType, save_impossible)


IF PY_MAJOR_VERSION > 2:
    #the string type will be used as first dump candidate!
    cdef _string_type = type(unicode())
    string_type = <void*>_string_type
    save_string_ptr = save_str3
    register_type(bytes(), save_bytes)
ELSE:
    cdef _string_type = type(bytes())
    string_type = <void*>_string_type
    save_string_ptr = save_str2
    register_type(unicode(), save_unicode)


# The Pickler class and its utilities
# -----------------------------------

ctypedef int (*pack_import_names_t)(Packer* p, module, name) except -1

cdef int simple_pack(Packer* p, module, name) except -1:
    p.dump(module)
    p.dump(name)


IF PY_MAJOR_VERSION > 2:
    cdef int mapped_pack(Packer* p, module, name) except -1:
        cdef PyObject *tmp
        tmp = PyDict_GetItem(name_mapping_3to2, (module, name))
        if tmp is not NULL:
            module, name = <object>tmp

        tmp = PyDict_GetItem(import_mapping_3to2, module)
        if tmp is not NULL:
            module = <object>tmp

        simple_pack(p, module, name)


@cython.auto_pickle(False)
cdef class Pickler:
    cdef:
        object file
        Packer *packer
        uint8_t protocol
        pack_import_names_t pack_import_names
        public dict dispatch_table
        public uint32_t last_refcount

    def __init__(
            self, file=None, protocol=MAX_PROTOCOL_VERSION, with_refs=True):
        IF PY_MAJOR_VERSION < 3:
            self.protocol = 2
            self.pack_import_names = simple_pack
        ELSE:
            if protocol < 0: protocol = MAX_PROTOCOL_VERSION
            protocol = min(protocol, MAX_PROTOCOL_VERSION)
            self.protocol = protocol
            if protocol == 2:
                self.pack_import_names = mapped_pack
            else:
                self.pack_import_names = simple_pack

        self.packer = new Packer(self, protocol, with_refs)
        self.dispatch_table = dispatch_table
        if protocol < 4:
            self.packer.min_string_size_for_ref = 5;
        else:
            self.packer.min_string_size_for_ref = 3;

        if file is None:
            self.file = OutputBuffer()
            self.packer.do_write = write_buffer
        elif hasattr(file, "c_pickle"):
            self.file = file.c_pickle()
            self.packer.do_write = write_external
        else:
            self.file = _FileLike(file)
            self.packer.do_write = write_file

    def __dealloc__(self):
        del self.packer

    cdef int pack_import1(self, uint8_t code, o) except -1:
        self.pack_import2(code, o.__module__, o.__qualname__)

    cdef int pack_import2(self, uint8_t code, module, name) except -1:
        cdef PyObject *rcode

        rcode = PyDict_GetItem(extension_registry, (module, name))
        if rcode is NULL:
            self.packer.pack_ext(code, 1)
            self.pack_import_names(self.packer, module, name)
        else:
            self.packer.pack_ext(code, 0)
            self.packer.write_int(<uint32_t><object>rcode)

    cdef int check_init(self) except -1:
        if self.file is None:
            raise PicklingError(
                "Pickler.__init__() was not called by "
                "{}.__init__()".format((self.__class__.__qualname__,)))

    def dump(self, obj, bool with_version=True):
        self.check_init()
        if with_version:
            self.packer.pack_version(self.protocol)
        try:
            self.packer.first_dump(obj)
        finally:
            self.last_refcount = self.packer.reset()
        return self

    def dumps(self, obj, bool with_version=True):
        self.check_init()
        (<OutputBuffer>self.file).reset()
        if with_version:
            self.packer.pack_version(self.protocol)
        try:
            self.packer.first_dump(obj)
        finally:
            self.last_refcount = self.packer.reset()

        return self.get_output_string()

    cpdef bytes get_output_string(self):
        return (<OutputBuffer>self.file).result()


# Unpickler Functions
# ----------------------------------

cdef int _load_slot_state(obj, state) except -1:
    cdef dict obj_value

    if PyTuple_Check(state) and PyTuple_GET_SIZE(state) == 2:
        # an object with __slots__
        obj_value = <dict>PyTuple_GET_ITEM(state, 1)
        for k, v in obj_value.items():
            setattr(obj, k, v)

        # an object with __slots__ and __dict__
        state = <object>PyTuple_GET_ITEM(state, 0)
        if state is not None:
            PyDict_Update(obj.__dict__, state)
        return 1
    return 0


cdef int _load_state(obj, state) except -1:
    if state is not None:
        set_state = getattr(obj, "__setstate__", None)
        if set_state is not None:
            set_state(state)
            return 0

        if not _load_slot_state(obj, state):
            PyDict_Update(obj.__dict__, state)
    return 0


cdef int _load_state_sequence(Unpacker *p, obj) except -1:
    item = p.load_object()
    if item is not _end_item:
        append = obj.append
        while item is not _end_item:
            append(item)
            item = p.load_object()
    return 0


cdef int _load_state_dict(Unpacker *p, obj) except -1:
    k = p.load_object()
    if k is not _end_item:
        setitem = obj.__setitem__
        while k is not _end_item:
            v = p.load_object()
            setitem(k, v)
            k = p.load_object()
    return 0


cdef object _load_object(Unpacker *p, obj):
    state = p.load_object()
    _load_state_sequence(p, obj)
    _load_state_dict(p, obj)
    _load_state(obj, state)
    return obj


cdef object load_object(Unpacker *p, uint8_t code, size_t size):
    cdef uint32_t stamp = p.get_stamp()
    constructor = p.load_object()
    constructor_args = p.load_object()
    try:
        obj = constructor(*constructor_args)
    except Exception as e:
        raise UnpicklingError(e, constructor, constructor_args)
    p.stamp(stamp, obj)
    return _load_object(p, obj)


cdef object load_object_new(Unpacker *p, uint8_t code, size_t size):
    cdef:
        uint32_t stamp = p.get_stamp()
        tuple cls_args

    cls_args = p.load_object()
    cls = cls_args[0]
    try:
        obj = GET_NEW(cls)(<PyTypeObject*>cls, cls_args[1:], NULL)
    except Exception as e:
        raise UnpicklingError(e, cls, cls_args)

    p.stamp(stamp, obj)
    return _load_object(p, obj)


cdef object load_object_fast(Unpacker *p, uint8_t code, size_t size):
    cdef:
        uint32_t stamp = p.get_stamp()
        tuple cls_args

    cls_args = p.load_object()
    cls = cls_args[0]
    try:
        obj = GET_NEW(cls)(<PyTypeObject*>cls, cls_args[1:], NULL)
    except Exception as e:
        raise UnpicklingError(e, cls, cls_args)

    p.stamp(stamp, obj)
    if size >= 3:
        state = p.load_object()
        if size >= 4:
            _load_state_sequence(p, obj)
            if size >= 5:
                _load_state_dict(p, obj)
        _load_state(obj, state)
    return obj


cdef object load_singleton(Unpacker *p, uint8_t code, size_t size):
    cdef uint32_t stamp = p.get_stamp()
    obj = (<Unpickler>p.unpickler).unpack_import(size)
    p.stamp(stamp, obj)
    return obj


cdef object load_oldstyle(Unpacker *p, uint8_t code, size_t size):
    cdef uint32_t stamp = p.get_stamp()
    obj = (<Unpickler>p.unpickler).unpack_import(size)()
    p.stamp(stamp, obj)
    obj.__dict__.update(p.load_object())
    return obj


cdef object load_initargs(Unpacker *p, uint8_t code, size_t size):
    cdef uint32_t stamp = p.get_stamp()
    obj = (<Unpickler>p.unpickler).unpack_import(size)
    init_args = p.load_object()
    obj = obj(*init_args)
    p.stamp(stamp, obj)
    return obj


cdef object load_end_item(Unpacker *p, uint8_t code, size_t size):
    return _end_item


cdef object load_ref(Unpacker* p, uint8_t code, size_t size):
    cdef:
        uint32_t ido
        PyObject* obj

    p.read32(&ido)
    obj = p.get_stamped_ref(ido)
    if obj is NULL:
        raise UnpicklingError("Invalid reference")

    return <object>obj


cdef object load_global(Unpacker* p, uint8_t code, size_t size):
    return (<Unpickler>p.unpickler).unpack_import(size)


cdef object load_global_object(Unpacker* p, uint8_t code, size_t size):
    cdef uint32_t stamp = p.get_stamp()
    obj = (<Unpickler>p.unpickler).unpack_import(size)
    p.stamp(stamp, obj)
    return obj


cdef object load_version(Unpacker* p, uint8_t code, size_t size):
    cdef uint8_t version
    p.read(<char*>&version, sizeof(version))
    (<Unpickler>p.unpickler).set_protocol(version)
    return p.load_object()


cdef object load_wrong_code(Unpacker* p, uint8_t code, size_t size):
    raise UnpicklingError("Unknown load code")


cdef _register_unpickle(unpack_t loader, codes, int offset=0):
    cdef size_t i
    for i in codes:
        unpickle_registry[i+offset] = loader

_register_unpickle(<unpack_t>load_wrong_code, range(0, 0x200))
_register_unpickle(load_uint4, range(0x80))
_register_unpickle(load_int4, range(0xe0, 0x100))
_register_unpickle(<unpack_t>load_ref, [0xc1])
_register_unpickle(load_uint8, [0xcc])
_register_unpickle(load_uint16, [0xcd])
_register_unpickle(load_uint32, [0xce])
_register_unpickle(load_uint64, [0xcf])
_register_unpickle(load_int8, [0xd0])
_register_unpickle(load_int16, [0xd1])
_register_unpickle(load_int32, [0xd2])
_register_unpickle(load_int64, [0xd3])
_register_unpickle(load_map4, range(0x80, 0x90))
_register_unpickle(load_map16,[0xde])
_register_unpickle(load_map32, [0xdf])
_register_unpickle(load_nil, [0xc0])
_register_unpickle(load_false, [0xc2])
_register_unpickle(load_true, [0xc3])
_register_unpickle(load_str4, range(0xa0, 0xc0))
_register_unpickle(load_str8, [0xd9])
_register_unpickle(load_str16, [0xda])
_register_unpickle(load_str32, [0xdb])
_register_unpickle(load_bin8, [0xc4])
_register_unpickle(load_bin16, [0xc5])
_register_unpickle(load_bin32, [0xc6])
_register_unpickle(load_array4, range(0x90, 0xa0))
_register_unpickle(load_array16, [0xdc])
_register_unpickle(load_array32, [0xdd])
_register_unpickle(load_float, [0xcb])
_register_unpickle(load_extf, [0xd4, 0xd5, 0xd6, 0xd7, 0xd8])
_register_unpickle(load_ext8, [0xc7])
_register_unpickle(load_ext16, [0xc8])
_register_unpickle(load_ext32, [0xc9])
_register_unpickle(<unpack_t>load_version, [VERSION], 0x100)
_register_unpickle(load_long, [LONG], 0x100)
_register_unpickle(load_list, [LIST], 0x100)
_register_unpickle(<unpack_t>load_global, [GLOBAL], 0x100)
_register_unpickle(<unpack_t>load_global_object, [GLOBAL_OBJECT], 0x100)
_register_unpickle(<unpack_t>load_object, [OBJECT], 0x100)
_register_unpickle(<unpack_t>load_object_new, [OBJECT_NEW, OBJECT_NEW_CUSTOM], 0x100)
_register_unpickle(<unpack_t>load_object_fast, [FAST_NEW], 0x100)
_register_unpickle(<unpack_t>load_singleton, [SINGLETON], 0x100)
_register_unpickle(<unpack_t>load_oldstyle, [OLD_STYLE], 0x100)
_register_unpickle(<unpack_t>load_initargs, [INIT_ARGS], 0x100)
_register_unpickle(<unpack_t>load_end_item, [END_OBJECT_ITEMS], 0x100)
_register_unpickle(load_bytes, [BYTES], 0x100)
_register_unpickle(load_unicode, [UNISTR], 0x100)


cdef class Unpickler

ctypedef object (*find_class_t)(Unpickler unpickler, module, name)

cdef object call_default_find_class(Unpickler unpickler, module, name):
    return unpickler.default_find_class(module, name)


cdef object call_sub_find_class(Unpickler unpickler, module, name):
    return unpickler._find_class(module, name)


ctypedef object (*default_find_class_t)(module, name)


cdef object simple_find_class(module, name):
    cdef PyObject* tmp
    tmp = PyDict_GetItem(modules, module)
    if tmp is NULL:
        try:
            __import__(module)
        except TypeError as e:
            e.args += (module, name)
            raise

        module = sys.modules[module]
    else:
        module = <object>tmp

    try:
        return getattr(module, name)
    except AttributeError:
        for n in name.split("."):
            module = getattr(module, n)
        return module


IF PY_MAJOR_VERSION > 2:
    cdef object mapped_find_class(module, name):
        cdef:
            PyObject* tmp

        tmp = PyDict_GetItem(name_mapping_2to3, (module, name))
        if tmp is not NULL:
            module, name = <object>tmp

        tmp = PyDict_GetItem(import_mapping_2to3, module)
        if tmp is not NULL:
            module = <object>tmp

        return simple_find_class(module, name)


@cython.auto_pickle(False)
cdef class Unpickler:
    cdef:
        object file
        Unpacker *unpacker
        object _find_class
        find_class_t call_find_class
        default_find_class_t default_find_class
        public uint32_t last_refcount
        public bool secure

    def __init__(self, file=b"", bool secure=False):
        self.unpacker = new Unpacker(self)
        self.secure = secure

        # this is complicated but faster than ordinary subclassing
        if isinstance(self.find_class, types.BuiltinMethodType):
            self.call_find_class = call_default_find_class
        else:
            self._find_class = self.find_class
            self.call_find_class = call_sub_find_class

        self.default_find_class = simple_find_class

        if isinstance(file, bytes):
            self.file = _BufferContainer().set(file)
            self.unpacker.do_read = read_buffer
        elif hasattr(file, "c_pickle"):
            self.file = file.c_pickle()
            self.unpacker.do_read = read_external
        else:
            self.file = _FileLike(file)
            self.unpacker.do_read = read_file


    def __dealloc__(self):
        del self.unpacker

    cdef int set_protocol(self, uint8_t protocol):
        IF PY_MAJOR_VERSION > 2:
            if protocol < 3:
                self.default_find_class = mapped_find_class
            else:
                self.default_find_class = simple_find_class
            if protocol < 4:
                self.unpacker.min_string_size_for_ref = 5;
            else:
                self.unpacker.min_string_size_for_ref = 3;

    cdef object unpack_import(self, size_t size):
        cdef:
            uint32_t rcode
            PyObject *key

        if size == 0:
            self.unpacker.read32(&rcode)
            ocode = <object><uint32_t>rcode
            key = PyDict_GetItem(extension_cache, ocode)
            if key is not NULL:
                return <object>key

            key = PyDict_GetItem(inverted_registry, ocode)
            if key is NULL:
                raise KeyError(rcode)

            module, name = <object>key
            obj = self.call_find_class(self, module, name)
            extension_cache[ocode] = obj
            return obj

        module = self.unpacker.load_object()
        name = self.unpacker.load_object()
        imported = self.call_find_class(self, module, name)
        if self.secure:
            self.verify_object(module, name, imported)

        return imported

    cdef int check_init(self) except -1:
        if self.file is None:
            raise UnpicklingError(
                "Unpickler.__init__() was not called by "
                "{}.__init__()".format((self.__class__.__name__,)))

    def find_class(self, str module, str name):
        return self.default_find_class(module, name)

    def load(self):
        self.check_init()
        try:
            return <object>self.unpacker.first_load()
        finally:
            self.last_refcount = self.unpacker.reset()

    def loads(self, bytes obj):
        self.check_init()
        (<_BufferContainer>self.file).set(obj)
        try:
            return <object>self.unpacker.first_load()
        finally:
            self.last_refcount = self.unpacker.reset()

    cpdef verify_object(self, module, name, obj):
        if (module not in secure_modules and obj not in secure_objects
                and PyDict_GetItem(extension_registry, (module, name)) is NULL):

            if getattr(obj, "__pickle_secure__", False):
                try:
                    secure_objects.add(obj)
                except TypeError:
                    pass
                return

            try:
                add_module = getattr(pickle_register, "add_"+module.replace(".", "_"))
            except AttributeError:
                pass
            else:
                add_module()
                if obj in secure_objects:
                    return

            logger.error("SecurityError %r %r", obj, module)
            print("SecurityError", obj, module)
            raise SecurityError("object not save for loading", obj, module)


cpdef dumps(obj, protocol=-1, with_refs=True):
    return Pickler(protocol=protocol, with_refs=with_refs)\
        .dump(obj).get_output_string()


cpdef dump(obj, file, protocol=-1):
    Pickler(file, protocol=protocol).dump(obj)


cpdef load(file, secure=False):
    cdef Unpickler unpickler = Unpickler(file, secure)
    return unpickler.load()


cpdef loads(bytes obj, secure=False):
    cdef Unpickler unpickler = Unpickler(obj, secure=True)
    return unpickler.load()
