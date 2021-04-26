#ifndef __PACK_HPP__
#define __PACK_HPP__

#include "pickle.hpp"


template<typename T> void to_buffer(unsigned char* buffer, T value) {
  encode(value);
  *(T*)&buffer[1] = value;
}


struct StringWriter {
  string output;

  void reset() {
    output.clear();
    if (output.capacity() < 8192)
      output.reserve(8192);
  }

  int write(void* data, size_t size) {
    /* the string memory management is much better than
       a manual call of self.output.reserve(...)!*/
    output.append((char*)data, size);
    return 1;
  }

  PyObject* result() {
    return PyBytes_FromStringAndSize(output.data(), output.size());
  }
};


struct Packer;

typedef void (*pack_t)(Packer* p, PyObject* o);

struct TypeMap : public unordered_map<PyObject*, pack_t> {
  pack_t get(PyObject* key) {
    iterator found = find(key);
    return found != end() ? found->second : NULL;
  }

  void register_type(PyObject* type, pack_t saver) {
    (*this)[type] = saver;
  }
};


struct BaseRefHandler {
  virtual bool save_ref(Packer* p, PyObject *o) = 0;
  virtual uint32_t reset() = 0;
  virtual ~BaseRefHandler() { }
};


struct DumyRefHandler : public BaseRefHandler {
  virtual bool save_ref(Packer* p, PyObject *o) {
    return false;
  }
  virtual uint32_t reset() {
    return 0;
  }
};


typedef unordered_map<PyObject*, uint32_t> refmap_t;

struct RefHandler : public BaseRefHandler {
  refmap_t refs;
  uint32_t ref_counter;
  PyObject* string_refs;       // for strings the python dict is more efficent

  RefHandler() : ref_counter(0) {
    string_refs = PyDict_New();
    if (!string_refs)
      throw PythonError();
  }

  ~RefHandler() {
    Py_XDECREF(string_refs);
  }

  virtual bool save_ref(Packer* p, PyObject *o);
  virtual uint32_t reset() {
    uint32_t val = ref_counter;
    ref_counter = 0;
    refs.clear();
    PyDict_Clear(string_refs);
    return val;
  }
};


/*
   template<typename T> void show_map(T x) {
   size_t count = x.bucket_count(), m = 0, i, s, c=0, a=0;


   for(i = 0; i < count; i++) {
    s = x.bucket_size(i);
    if (s) {
      if (m < s) m = s;
      c++;
      a += s;
    }
   }

   printf("bucket count: %lu\n", count);
   printf("load factor: %f\n", x.load_factor());
   printf("max bucket size: %lu\n", m);
   printf("avg bucket size: %f\n", (float)a/(float)c);
   printf("object count: %lu\n", a);
   printf("non empty bucket count: %lu\n", c);
   }
 */

static void* string_type;
static pack_t save_string_ptr;
static pack_t save_object_ptr;
static TypeMap pickle_registry;


struct Packer {
  PyObject *pickler;
  write_t do_write;
  int protocol;
  BaseRefHandler *refhandler;
  size_t min_string_size_for_ref;

  void set_refs(bool with_refs) {
    delete refhandler;
    if (with_refs)
      refhandler = new RefHandler();
    else
      refhandler = new DumyRefHandler();
  }

  Packer(PyObject* pickler, int protocol, bool with_refs)
    : pickler(pickler), protocol(protocol), refhandler(NULL),
      min_string_size_for_ref(MIN_STRING_SIZE_FOR_REF) {
    set_refs(with_refs);
  }

  ~Packer()  {
    delete refhandler;
  }

  uint32_t reset() {
    return refhandler->reset();
  }

  void write(const void* value, size_t size) {
    if (do_write(pickler, (void*)value, size) == -1)
      throw PythonError();
  }

  template <typename T> void write_int(T value) {
    encode(value);
    if (do_write(pickler, &value, sizeof(value)) == -1)
      throw PythonError();
  }

  template <typename T> bool pack8(T value) {
    if (sizeof(T) > 1 && (value < -128 || value > 0xFF))
      return false;

    int8_t v = (int8_t)value;
    if (-32 <= value && value <= 0x7F) {
      write(&v, sizeof(v));
      return true;
    }

    if (value < -32) {
      unsigned char buf[2] = {0xd0, (unsigned char)v};
      write(buf, sizeof(buf));
      return true;
    }

    // value > 0x7f
    unsigned char buf[2] = {0xcc, (unsigned char)v};
    write(buf, sizeof(buf));
    return true;
  }


  template <typename T> bool pack16(T value) {
    if (sizeof(T) > 2 && (value < -32768 || value > 0xFFFF))
      return false;

    if (pack8(value))
      return true;

    if (value < 0x0FFF) {
      unsigned char buf[3] = { 0xd1 };
      to_buffer(buf, (uint16_t)value);
      write(buf, sizeof(buf));
      return true;
    }

    // value >= 0
    unsigned char buf[3] = { 0xcd };
    to_buffer(buf, (uint16_t)value);
    write(buf, sizeof(buf));
    return true;
  }

  template <typename T> bool pack32(T value) {
    if (sizeof(T) > 4 && (value < -2147483648 || value > 0xFFFFFFFF))
      return false;

    if (pack16(value))
      return true;

    if (value <= 0x0FFFFFFF) {
      unsigned char buf[5] = { 0xd2 };
      to_buffer(buf, (uint32_t)value);
      write(buf, sizeof(buf));
      return true;
    }

    unsigned char buf[5] = { 0xce };
    to_buffer(buf, (uint32_t)value);
    write(buf, sizeof(buf));
    return true;
  }

  template<typename T> void pack64(T value) {
    if (pack32(value))
      return;

    if (value < 0x0FFFFFFFFFFFFFFF) {
      unsigned char buf[9] = { 0xd3 };
      to_buffer(buf, (uint64_t)value);
      write(buf, sizeof(buf));
      return;
    }

    unsigned char buf[9] = { 0xcf };
    to_buffer(buf, (uint64_t)value);
    write(buf, sizeof(buf));
  }

  template<typename T> void pack_int(T value) {
    if (sizeof(T) == 2) {
      pack16(value);
    }

    if (sizeof(T) == 4) {
      pack32(value);
    }

    if (sizeof(T) == 8) {
      pack64(value);
    }
  }

  void pack_nil() {
    static const uint8_t v = 0xc0;
    write(&v, sizeof(v));
  }

  void pack_true() {
    static const uint8_t v = 0xc3;
    write(&v, sizeof(v));
  }

  void pack_false() {
    static const uint8_t v = 0xc2;
    write(&v, sizeof(v));
  }

  void pack_bool(bool value) {
    value ? pack_true() : pack_false();
  }

  void pack_double(double d) {
    unsigned char buf[9] = { 0xcb };
    *(double*)&buf[1] = (double)d;
    encode(*(uint64_t*)&buf[1]);
    write(buf, sizeof(buf));
  }

  void pack_array(size_t n) {
    if(n < 16) {
      unsigned char d = 0x90 | n;
      write(&d, sizeof(d));
    } else if(n < 0xFFFF) {
      unsigned char buf[3] = {0xdc};
      to_buffer(buf, (uint16_t)n);
      write(buf, sizeof(buf));
    } else {
      unsigned char buf[5] = {0xdd};
      to_buffer(buf, (uint32_t)n);
      write(buf, sizeof(buf));
    }
  }

  void pack_map(size_t n) {
    if (n < 16) {
      unsigned char d = 0x80 | n;
      write(&d, sizeof(d));
    } else if(n < 65536) {
      unsigned char buf[3] = { 0xde };
      to_buffer(buf, (uint16_t)n);
      write(buf, sizeof(buf));
    } else {
      unsigned char buf[5] = { 0xdf };
      to_buffer(buf, (uint32_t)n);
      write(buf, sizeof(buf));
    }
  }

  void pack_ext(int8_t typecode, size_t l) {
    switch(l) {
    case 1:
    {
      unsigned char buf[2] = { 0xd4, (unsigned char)typecode };
      write(buf, sizeof(buf));
      return;
    }
    case 2:
    {
      unsigned char buf[2] = { 0xd5, (unsigned char)typecode };
      write(buf, sizeof(buf));
      return;
    }

    case 4:
    {
      unsigned char buf[2] = { 0xd6, (unsigned char)typecode };
      write(buf, sizeof(buf));
      return;
    }

    case 8:
    {
      unsigned char buf[2] = { 0xd7, (unsigned char)typecode };
      write(buf, sizeof(buf));
      return;
    }

    case 16:
    {
      unsigned char buf[2] = { 0xd8, (unsigned char)typecode };
      write(buf, sizeof(buf));
      return;
    }
    }

    if (l < 256) {
      unsigned char buf[3] = { 0xc7, (unsigned char)l, (unsigned char)typecode };
      write(buf, sizeof(buf));
    } else if (l < 65536) {
      unsigned char buf[4] = { 0xc8, 0, 0, (unsigned char)typecode };
      to_buffer(buf, (uint16_t)l);
      write(buf, sizeof(buf));
    } else {
      unsigned char buf[6] = { 0xc9, 0, 0, 0, 0, (unsigned char)typecode };
      to_buffer(buf, (uint32_t)l);
      write(buf, sizeof(buf));
    }
  }

  inline void pack_bin(size_t l) {
    if (l < 256) {
      unsigned char buf[2] = {0xc4, (unsigned char)l};
      write(buf, sizeof(buf));
    } else if (l < 65536) {
      unsigned char buf[3] = {0xc5};
      to_buffer(buf, (uint16_t)l);
      write(buf, sizeof(buf));
    } else {
      unsigned char buf[5] = {0xc6};
      to_buffer(buf, (uint32_t)l);
      write(buf, sizeof(buf));
    }
  }

  inline void pack_str(size_t l) {
    if (l < 32) {
      unsigned char d = 0xa0 | (uint8_t)l;
      write(&d, sizeof(d));
    } else if (l < 256) {
      unsigned char buf[2] = {0xd9, (uint8_t)l};
      write(buf, sizeof(buf));
    } else if (l < 65536) {
      unsigned char buf[3] = { 0xda };
      to_buffer(buf, (uint16_t)l);
      write(buf, sizeof(buf));
    } else {
      unsigned char buf[5] = { 0xdb };
      to_buffer(buf, (uint32_t)l);
      write(buf, sizeof(buf));
    }
  }

  void pack_version(uint8_t version) {
    pack_ext(VERSION, 1);
    write(&version, sizeof(version));
  }

  bool save_ref(PyObject *o) {
    return refhandler->save_ref(this, o);
  }

  inline void dump(PyObject *o) {
    PyTypeObject *type = Py_TYPE(o);
    if (type == (PyTypeObject*)string_type) {
      // A little optimation: there are many strings
      save_string_ptr(this, o);
      return;
    }

    pack_t packer = pickle_registry.get((PyObject*)type);
    if (!packer) {
      save_object_ptr(this, o);
      return;
    }

    packer(this, o);
  }

  int first_dump(PyObject* o) {
    // only for cython to catch errors
    try {
      dump(o);
    }
    catch(PythonError) {
      return -1;
    }
    catch(...) {
      PyErr_SetNone(PyExc_RuntimeError);
      return -1;
    }
    return 0;
  }
};


inline bool RefHandler::save_ref(Packer* p, PyObject *o) {
  if (o->ob_refcnt == 1) {
    ++ref_counter;
    // there will be no reference => don't save any
    return false;
  }

  if (PyUnicode_Check(o) || PyString_Check(o)) {
    PyObject* c = PyDict_GetItem(string_refs, o);
    if (!c) {
      PyObject* i = PyInt_FromLong(++ref_counter);
      PyDict_SetItem(string_refs, o, i);
      Py_XDECREF(i);
      return false;
    }

    unsigned char buf[5] = {0xc1};
    uint32_t ref = PyInt_AS_LONG(c);
    to_buffer(buf, ref);
    p->write(buf, sizeof(buf));
    return true;
  }
  else {
    uint32_t& refid = refs[o];
    if (!refid) {
      refid = ++ref_counter;
      return false;
    }

    unsigned char buf[5] = {0xc1};
    to_buffer(buf, refid);
    p->write(buf, sizeof(buf));
    return true;
  }
}


inline void save_none(Packer* p, PyObject* o) {
  p->pack_nil();
}

inline void save_bool(Packer* p, PyObject* o) {
  p->pack_bool(o == Py_True);
}

inline void save_int(Packer* p, PyObject* o) {
  p->pack_int(PyInt_AS_LONG(o));
}

inline void save_float(Packer* p, PyObject* o) {
  p->pack_double(PyFloat_AS_DOUBLE(o));
}

inline void save_tuple(Packer* p, PyObject* o) {
  if (p->save_ref(o)) return;

  Py_ssize_t size, i;
  size = PyTuple_GET_SIZE(o);
  p->pack_array(size);
  for(i = 0; i < size; i++) {
    p->dump(PyTuple_GET_ITEM(o, i));
  }
}

inline void save_list(Packer* p, PyObject* o) {
  if (p->save_ref(o)) return;

  Py_ssize_t size, i;
  size = PyList_GET_SIZE(o);
  p->pack_ext(LIST, size);
  for(i = 0; i < size; i++) {
    p->dump(PyList_GET_ITEM(o, i));
  }
}


inline void _pack_dict(Packer* p, PyObject* o) {
  Py_ssize_t i = 0;
  PyObject *key, *value;
  while (PyDict_Next(o, &i, &key, &value)) {
    p->dump(key);
    p->dump(value);
  }
}

inline void  save_dict(Packer* p, PyObject* o) {
  if (p->save_ref(o)) return;
  Py_ssize_t size = PyDict_Size(o);
  p->pack_map(size);
  _pack_dict(p, o);
}


inline void save_bytes(Packer* p, PyObject* o) {
  Py_ssize_t size = PyBytes_GET_SIZE(o);
  if (size > p->min_string_size_for_ref && p->save_ref(o)) return;
  p->pack_ext(BYTES, size);
  p->write(PyBytes_AS_STRING(o), size);
}


#if PY_MAJOR_VERSION > 2

inline void save_str3(Packer* p, PyObject* o) {
  Py_ssize_t size = PyUnicode_GET_LENGTH(o);
  PyObject *encoded = NULL;

  if (size > p->min_string_size_for_ref && p->save_ref(o)) return;

  const char* buffer = PyUnicode_AsUTF8AndSize(o, &size);
  if (!buffer) {
    // Try with surrogates
    PyErr_Clear();
    encoded = PyUnicode_AsEncodedString(o, "utf8", "surrogatepass");
    if (!encoded)
      throw PythonError();

    size = PyBytes_GET_SIZE(encoded);
    buffer = PyBytes_AS_STRING(encoded);
  }

  try {
    if (PyUnicode_CHECK_INTERNED(o)) {
      p->pack_bin(size);
    }
    else {
      p->pack_str(size);
    }

    p->write(buffer, size);
  }
  catch(...) {
    Py_XDECREF(encoded);
    throw;
  }
}

#else

inline void save_str2(Packer* p, PyObject* o) {
  Py_ssize_t size = PyBytes_GET_SIZE(o);
  if (size > p->min_string_size_for_ref && p->save_ref(o)) return;

  if (PyString_CHECK_INTERNED(o))
    p->pack_bin(size);
  else
    p->pack_str(size);

  p->write(PyBytes_AS_STRING(o), size);
}
#endif

inline void save_unicode(Packer* p, PyObject* o) {
  Py_ssize_t size = PyUnicode_GET_LENGTH(o);
  if (size > p->min_string_size_for_ref && p->save_ref(o)) return;

  PyObject *encoded = PyUnicode_AsUTF8String(o);
  if (!encoded)
    throw PythonError();

  try {
    size = PyBytes_GET_SIZE(encoded);
    p->pack_ext(UNISTR, size);
    p->write(PyBytes_AS_STRING(encoded), size);
  }
  catch(...) {
    Py_DECREF(encoded);
    throw;
  }
  Py_DECREF(encoded);
}

#endif
