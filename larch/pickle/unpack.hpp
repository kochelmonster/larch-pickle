#ifndef __UNPACK_HPP__
#define __UNPACK_HPP__

#include "pickle.hpp"
#include <boost/shared_array.hpp>

struct Unpacker;

typedef PyObject* (*unpack_t)(Unpacker* p, uint8_t code, size_t size);

static unpack_t unpickle_registry[0x200];


struct StringReader {
  char* data;
  size_t pos, size;

  inline void read(void* buffer, size_t read_size) {
    if (pos+read_size > size) {
      PyErr_SetNone(PyExc_EOFError);
      throw PythonError();
    }
    memcpy(buffer, data+pos, read_size);
    pos += read_size;
  }
};


struct PointerPage {
  shared_array<PyObject*> refs;

  PointerPage() : refs(new PyObject*[1024]) {
    memset(refs.get(), 0, sizeof(PyObject*)*1024);
  }
};

inline uint32_t page(uint32_t key) {
  return key >> 10;
}

inline uint32_t index(uint32_t key) {
  return key & 0x3ff;
}


struct UnrefMap : public vector<PointerPage> {
  uint32_t ref_counter;

  UnrefMap() : ref_counter(1) {
    resize(1);
    data()[0].refs[0] = NULL;
  }
  ~UnrefMap() {
    reset();
  }

  PyObject* get(uint32_t key) {
    if (key < ref_counter) {
      return (*this)[page(key)].refs[index(key)];
    }
    return (*this)[0].refs[0];
  }

  inline uint32_t get_stamp() {
    if (ref_counter >= size()<<10) {
      size_t new_alloc = (page(ref_counter) >> 2) + 2;
      resize(size()+(new_alloc > 100 ? 100 : new_alloc));
    }
    return ref_counter++;
  }

  inline void stamp(uint32_t refid, PyObject* o) {
    Py_INCREF(o);
    (*this)[page(refid)].refs[index(refid)] = o;
  }

  inline void change_stamp(uint32_t refid, PyObject* o) {
    (*this)[page(refid)].refs[index(refid)] = o;
  }

  uint32_t reset() {
    uint32_t i, j, end, val = ref_counter-1;
    PyObject **p;
    for(i = 0; i < ref_counter; i += 1024) {
      p = &data()[page(i)].refs[0];
      end = i + 1024;
      if (end > ref_counter) end = ref_counter;
      for(j = i; j < end; j++, p++) {
        Py_CLEAR(*p);
        *p = NULL;
      }
    }
    ref_counter = 1;
    return val;
  }
};

#define SIZE8 p->read8((uint8_t*)&size)
#define SIZE16 p->read16((uint16_t*)&size)
#define SIZE32 p->read32((uint32_t*)&size)


struct Unpacker {
  typedef vector<char> buffer_t;
  PyObject *unpickler;
  read_t do_read;
  UnrefMap refs;
  buffer_t read_buffer;
  size_t min_string_size_for_ref;

  Unpacker(PyObject *unpickler):
      unpickler(unpickler), min_string_size_for_ref(MIN_STRING_SIZE_FOR_REF) {
    reset();
  }

  uint32_t reset() {
    return refs.reset();
  }

  inline PyObject* get_stamped_ref(uint32_t ref) {
    return refs.get(ref);
  }

  inline uint32_t get_stamp() {
    return refs.get_stamp();
  }

  inline void stamp(uint32_t ref, PyObject* o) {
    if (ref)
      refs.stamp(ref, o);
  }

  inline void stamp(PyObject* o) {
    stamp(get_stamp(), o);
  }

  inline void change_stamp(uint32_t ref, PyObject* o) {
    if (ref)
      refs.change_stamp(ref, o);
  }

  inline void read(void* data, size_t size) {
    if (do_read(unpickler, data, size) == -1)
      throw PythonError();
  }

  template<typename T> inline void read(T& value) {
    if (do_read(unpickler, &value, sizeof(value)) == -1)
      throw PythonError();
    decode(value);
  }

  inline void read8(uint8_t* value) {
    if (do_read(unpickler, value, sizeof(uint8_t)) == -1)
      throw PythonError();
  }
  inline void read16(uint16_t* value) {
    read(*value);
  }
  inline void read32(uint32_t* value) {
    read(*value);
  }
  inline void read64(uint64_t* value) {
    read(*value);
  }


  PyObject* load() {
    uint8_t code;
    read8(&code);
    PyObject *result = unpickle_registry[code](this, code, 0);
    if (!result)
      throw PythonError();
    return result;
  }

  PyObject* first_load() {
    // only for cython to catch errors
    try {
      return load();
    }
    catch(PythonError) {
      return NULL;
    }
    catch(...) {
      PyErr_SetNone(PyExc_RuntimeError);
      return NULL;
    }
  }
};

inline PyObject* load_uint4(Unpacker *p, uint8_t code, size_t size) {
  return PyInt_FromLong(code);
}

inline PyObject* load_int4(Unpacker *p, uint8_t code, size_t size) {
  return PyInt_FromLong((int8_t)code);
}

inline PyObject* load_uint8(Unpacker *p, uint8_t code, size_t size) {
  uint8_t v;
  p->read8(&v);
  return PyInt_FromLong(v);
}

inline PyObject* load_int8(Unpacker *p, uint8_t code, size_t size) {
  int8_t v;
  p->read8((uint8_t*)&v);
  return PyInt_FromLong(v);
}

inline PyObject* load_uint16(Unpacker *p, uint8_t code, size_t size) {
  uint16_t v;
  p->read16(&v);
  return PyInt_FromLong(v);
}

inline PyObject* load_int16(Unpacker *p, uint8_t code, size_t size) {
  int16_t v;
  p->read16((uint16_t*)&v);
  return PyInt_FromLong(v);
}

inline PyObject* load_uint32(Unpacker *p, uint8_t code, size_t size) {
  uint32_t v;
  p->read32(&v);

  if (sizeof(long) == sizeof(v))
    return PyLong_FromUnsignedLong(v);

  return PyInt_FromLong(v);
}

inline PyObject* load_int32(Unpacker *p, uint8_t code, size_t size) {
  int32_t v;
  p->read32((uint32_t*)&v);
  return PyInt_FromLong(v);
}

inline PyObject* load_uint64(Unpacker *p, uint8_t code, size_t size) {
  uint64_t v;
  p->read64(&v);
  return PyLong_FromUnsignedLongLong(v);
}

inline PyObject* load_int64(Unpacker *p, uint8_t code, size_t size) {
  int64_t v;
  p->read64((uint64_t*)&v);

  if (sizeof(long) == sizeof(v))
    return PyInt_FromLong(v);

  return PyLong_FromLongLong(v);
}

inline PyObject* load_float(Unpacker *p, uint8_t code, size_t size) {
  union {
    double d;
    uint64_t i;
  };
  p->read64(&i);
  return PyFloat_FromDouble(d);
}

inline PyObject* load_nil(Unpacker *p, uint8_t code, size_t size) {
  Py_INCREF(Py_None);
  return Py_None;
}

inline PyObject* load_false(Unpacker *p, uint8_t code, size_t size) {
  Py_INCREF(Py_False);
  return Py_False;
}

inline PyObject* load_true(Unpacker *p, uint8_t code, size_t size) {
  Py_INCREF(Py_True);
  return Py_True;
}

inline PyObject* _load_array(Unpacker *p, size_t size) {
  size_t i = 0, capacity = size > 0xFFFF ? 0xFFFF : size;
  PyObject *r, *o;
  uint32_t stamp = p->get_stamp();

  r = PyTuple_New(capacity);
  if (!r)
    throw PythonError();

  try {
    while(i < size) {
      if (i >= capacity) {
        capacity = i << 1;
        if (capacity > size) capacity = size;

        if (_PyTuple_Resize(&r, capacity) < 0) {
          // will raise error if a recursive tuple declaration occurs
          // because of obj_refcount > 1
          throw PythonError();
        }
      }
      p->change_stamp(stamp, r); // r may have change

      for(; i < capacity; i++) {
        o = p->load();
        PyTuple_SET_ITEM(r, i, o);
      }
    }
  }
  catch(...) {
    Py_XDECREF(r);
    p->change_stamp(stamp, NULL);
    throw;
  }
  p->stamp(stamp, r); // increases the refcount (change_stamp does not!)
  return r;
}

inline PyObject* load_array4(Unpacker *p, uint8_t code, size_t size) {
  return _load_array(p, code-0x90);
}

inline PyObject* load_array16(Unpacker *p, uint8_t code, size_t size) {
  SIZE16;
  return _load_array(p, size);
}

inline PyObject* load_array32(Unpacker *p, uint8_t code, size_t size) {
  SIZE32;
  return _load_array(p, size);
}

inline PyObject* load_list(Unpacker *p, uint8_t code, size_t size) {
  size_t i, save_size = size > 0xFFFF ? 0xFFFF : size;
  PyObject *r, *o;

  /* to defend dos attacks leading to uncontrolled allocation
     only maximal 0xFFFF items will be preallocated. */
  r = PyList_New(save_size);
  if (!r)
    throw PythonError();

  try {
    p->stamp(r);
    for(i = 0; i < save_size; i++) {
      o = p->load();
      PyList_SET_ITEM(r, i, o);
    }

    // very unprobable
    for(; i < size; i++) {
      o = p->load();
      PyList_Append(r, o);
    }
  }
  catch(...) {
    Py_XDECREF(r);
    throw;
  }
  return r;
}

inline PyObject* load_long(Unpacker *p, uint8_t code, size_t size) {
  PyObject *buffer = PyBytes_FromStringAndSize(NULL, size);
  if (!buffer)
    throw PythonError();

  PyObject *result = NULL;
  try {
    p->read(PyBytes_AS_STRING(buffer), size);

    result = _PyLong_FromByteArray
               ((unsigned char*)PyBytes_AS_STRING(buffer), size, 1, 1);

    if (!result)
      throw PythonError();

    p->stamp(result);
  }
  catch(...) {
    Py_DECREF(buffer);
    Py_XDECREF(result);
    throw;
  }

  Py_DECREF(buffer);
  return result;
}


inline PyObject* _load_ext(Unpacker *p, size_t size) {
  uint8_t typecode;
  p->read8(&typecode);
  return unpickle_registry[0x100+typecode](p, typecode, size);
}

inline PyObject* load_extf(Unpacker *p, uint8_t code, size_t size) {
  return _load_ext(p, 1 << (code-0xd4));
}

inline PyObject* load_ext8(Unpacker *p, uint8_t code, size_t size) {
  SIZE8;
  return _load_ext(p, size);
}

inline PyObject* load_ext16(Unpacker *p, uint8_t code, size_t size) {
  SIZE16;
  return _load_ext(p, size);
}

inline PyObject* load_ext32(Unpacker *p, uint8_t code, size_t size) {
  SIZE32;
  return _load_ext(p, size);
}


inline PyObject* _load_map(Unpacker* p, size_t size) {
  size_t i;
  PyObject *r = PyDict_New(), *key = NULL, *value = NULL;
  if (!r)
    throw PythonError();

  try {
    p->stamp(r);
    for (i = 0; i < size; i++) {
      key = p->load();
      value = p->load();
      if (PyDict_SetItem(r, key, value) < 0)
        throw PythonError();

      Py_DECREF(key);
      Py_DECREF(value);
      key = value = NULL;
    }
  }
  catch(...) {
    Py_XDECREF(key);
    Py_XDECREF(value);
    Py_XDECREF(r);
    throw;
  }

  return r;
}

inline PyObject* load_map4(Unpacker* p, uint8_t code, size_t size) {
  return _load_map(p, code-0x80);
}

inline PyObject* load_map16(Unpacker* p, uint8_t code, size_t size) {
  SIZE16;
  return _load_map(p, size);
}

inline PyObject* load_map32(Unpacker* p, uint8_t code, size_t size) {
  SIZE32;
  return _load_map(p, size);
}


inline PyObject* _load_bytes(Unpacker* p, size_t size, int interned) {
  PyObject* result = PyBytes_FromStringAndSize(NULL, size);
  if (!result)
    throw PythonError();

  try {
    p->read(PyBytes_AS_STRING(result), size);

#if PY_MAJOR_VERSION < 3
    if (interned)
      PyString_InternInPlace(&result);
#endif

    if (size > p->min_string_size_for_ref)
      p->stamp(result);
  }
  catch(...) {
    Py_XDECREF(result);
    throw;
  }
  return result;
}


inline PyObject* _load_unicode(Unpacker* p, size_t size, int interned) {
  PyObject* result = NULL;

  p->read_buffer.reserve(size);
  try {
    p->read(p->read_buffer.data(), size);
    result = PyUnicode_DecodeUTF8(p->read_buffer.data(), size, "surrogatepass");
    if (!result)
      throw PythonError();

#if PY_MAJOR_VERSION > 2
    if (interned)
      PyUnicode_InternInPlace(&result);
#endif

    if (PyUnicode_GET_LENGTH(result) > p->min_string_size_for_ref)
      p->stamp(result);
  }
  catch(...) {
    Py_XDECREF(result);
    throw;
  }

  return result;
}

inline PyObject* load_unicode(Unpacker* p, uint8_t code, size_t size) {
  return _load_unicode(p, size, 0);
}

#if PY_MAJOR_VERSION > 2
#define _load_str _load_unicode
#else
#define _load_str _load_bytes
#endif

inline PyObject* load_str4(Unpacker* p, uint8_t code, size_t size) {
  return _load_str(p, code-0xa0, 0);
}

inline PyObject* load_str8(Unpacker* p, uint8_t code, size_t size) {
  SIZE8;
  return _load_str(p, size, 0);
}

inline PyObject* load_str16(Unpacker* p, uint8_t code, size_t size) {
  SIZE16;
  return _load_str(p, size, 0);
}

inline PyObject* load_str32(Unpacker* p, uint8_t code, size_t size) {
  SIZE32;
  return _load_str(p, size, 0);
}

inline PyObject* load_bin8(Unpacker* p, uint8_t code, size_t size) {
  SIZE8;
  return _load_str(p, size, 1);
}

inline PyObject* load_bin16(Unpacker* p, uint8_t code, size_t size) {
  SIZE16;
  return _load_str(p, size, 1);
}

inline PyObject* load_bin32(Unpacker* p, uint8_t code, size_t size) {
  SIZE32;
  return _load_str(p, size, 1);
}

inline PyObject* load_bytes(Unpacker* p, uint8_t code, size_t size) {
  PyObject* bin = PyBytes_FromStringAndSize(NULL, size);
  if (!bin)
    throw PythonError();

  try {
    p->read(PyBytes_AS_STRING(bin), size);
    if (size > p->min_string_size_for_ref) p->stamp(bin);
  } catch(...) {
    Py_XDECREF(bin);
    throw;
  }
  return bin;
}

/*
 #include <unistd.h>
 #include <signal.h>
   void myterminate(int sig) {
   printf("sigegv exception: %i\n", getpid());
   sleep(1000);
   }


   struct SetTerminate {
   SetTerminate() {
    signal(SIGSEGV, myterminate);
   }
   };

   SetTerminate s;
 */
#endif
