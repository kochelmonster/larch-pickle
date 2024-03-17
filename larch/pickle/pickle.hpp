#ifndef __PICKLE_HPP__
#define __PICKLE_HPP__

#include <boost/cstdint.hpp>
#include <boost/unordered_map.hpp>
#include <boost/container/string.hpp>
#include <boost/container/vector.hpp>
#include <boost/endian/conversion.hpp>
#include <Python.h>
#include <stdio.h>

using namespace boost;
using namespace boost::endian;
using namespace boost::container;

/*#define encode native_to_little
  #define decode little_to_native*/
#define encode native_to_big_inplace
#define decode big_to_native_inplace

#define MIN_STRING_SIZE_FOR_REF 3

enum EXT_TYPES {
  VERSION=0, LONG, LIST, OBJECT, OBJECT_NEW, GLOBAL, SINGLETON,
  OLD_STYLE, INIT_ARGS, END_OBJECT_ITEMS, BYTES, UNISTR, OBJECT_NEW_CUSTOM,
  GLOBAL_OBJECT, FAST_NEW, COUNT_EXT_TYPES
};


#ifndef PyUnicode_GET_LENGTH
#define PyUnicode_GET_LENGTH PyUnicode_GET_SIZE
#endif


typedef int (*write_t)(PyObject* p, void* data, size_t size);
typedef int (*read_t)(PyObject* p, void* data, size_t size);


// typedef void (*debug_t)(const char* msg, PyObject *o, long v);
// static debug_t debug;


class PythonError: std::exception {
};

inline void throw_python_error() {
  throw PythonError();
}

#define GET_NEW(obj) (((PyTypeObject*)(obj))->tp_new)

#endif
