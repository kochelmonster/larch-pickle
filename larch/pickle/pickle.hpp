#ifndef __PICKLE_HPP__
#define __PICKLE_HPP__

#include <Python.h>
#include <stdio.h>

#include <boost/container/string.hpp>
#include <boost/container/vector.hpp>
#include <boost/cstdint.hpp>
#include <boost/endian/conversion.hpp>
#include <boost/unordered_map.hpp>

using namespace boost;
using namespace boost::endian;
using namespace boost::container;

/*#define encode native_to_little
  #define decode little_to_native*/
#define encode native_to_big_inplace
#define decode big_to_native_inplace

#define MIN_STRING_SIZE_FOR_REF 3

enum EXT_TYPES {
  VERSION = 0,
  LONG,
  LIST,
  OBJECT,
  OBJECT_NEW,
  GLOBAL,
  SINGLETON,
  OLD_STYLE,
  INIT_ARGS,
  END_OBJECT_ITEMS,
  BYTES,
  UNISTR,
  OBJECT_NEW_CUSTOM,
  GLOBAL_OBJECT,
  FAST_NEW,
  COUNT_EXT_TYPES
};

#ifndef PyUnicode_GET_LENGTH
#define PyUnicode_GET_LENGTH PyUnicode_GET_SIZE
#endif

/* Python 2/3 compatibility macros */
#if PY_MAJOR_VERSION >= 3
  #define PyString_Check PyUnicode_Check
  #define PyInt_FromLong PyLong_FromLong
  #define PyInt_AS_LONG PyLong_AsLong
#endif

typedef int (*write_t)(PyObject* p, void* data, size_t size);
typedef int (*read_t)(PyObject* p, void* data, size_t size);

// typedef void (*debug_t)(const char* msg, PyObject *o, long v);
// static debug_t debug;

class PythonError : std::exception {};

inline void throw_python_error() { throw PythonError(); }

#define GET_NEW(obj) (((PyTypeObject*)(obj))->tp_new)

#if PY_MINOR_VERSION < 13
inline int CPyLong_AsByteArray(PyLongObject* v, unsigned char* bytes, size_t n,
                               int little_endian, int is_signed) {
  return _PyLong_AsByteArray(v, bytes, n, little_endian, is_signed);
}
#else
inline int CPyLong_AsByteArray(PyLongObject* v, unsigned char* bytes, size_t n,
                               int little_endian, int is_signed) {
  return _PyLong_AsByteArray(v, bytes, n, little_endian, is_signed, 1);
}
#endif

#endif
