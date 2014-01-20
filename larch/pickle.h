#ifndef __PYX_HAVE__larch__pickle
#define __PYX_HAVE__larch__pickle


#ifndef __PYX_HAVE_API__larch__pickle

#ifndef __PYX_EXTERN_C
  #ifdef __cplusplus
    #define __PYX_EXTERN_C extern "C"
  #else
    #define __PYX_EXTERN_C extern
  #endif
#endif

__PYX_EXTERN_C DL_IMPORT(PyObject) *statistics;

#endif /* !__PYX_HAVE_API__larch__pickle */

#if PY_MAJOR_VERSION < 3
PyMODINIT_FUNC initpickle(void);
#else
PyMODINIT_FUNC PyInit_pickle(void);
#endif

#endif /* !__PYX_HAVE__larch__pickle */
