import copyreg

secure_objects = set([copyreg._reconstructor])
secure_modules = {"time", "uuid", "string", "re",
                  "difflib", "textwrap", "unicodedata", "strinprep", "codecs", "datetime",
                  "zoneinfo", "calendar", "collections", "collections.abc",
                  "heapq", "bisect", "array", "weakref", "types", "copy", "reprlib", "enum",
                  "graphlib", "numbers", "math", "cmath", "decimal", "fractions", "random",
                  "statistics", "errno", "html", "html.entities", "http.cookies", "Cookie",
                  "http.cookiejar", "ipaddress",
                  "larch.reactive.proxy", "larch.reactive.rcollections"}


def secure_unpickle(obj):
    secure_objects.add(obj)
    return obj


def hashable(obj):
    try:
        hash(obj)
        return True
    except TypeError:
        return False


def make_secure(module, unsecure):
    unsecure = frozenset(unsecure.split())
    secure = (getattr(module, n) for n in dir(module)
              if not (n.startswith("__") or n in unsecure))
    secure_objects.update(o for o in secure if hashable(o))


def add_builtins():
    import builtins
    unsecure = """breakpoint compile delattr eval exec exit input locals
    globals memoryview open print quit setattr staticmethod classmethod
    super vars"""
    make_secure(builtins, unsecure)


add___builtin__ = add_builtins


def add_operator():
    import operator
    make_secure(operator, "methodcaller delitem setitem")


def add__operator():
    import _operator
    make_secure(_operator, "methodcaller delitem setitem")


def add_os():
    import os
    secure_objects.update([os.stat_result, os.statvfs_result])


def add_extension_by_hash(module, name):
    from hashlib import md5
    code = int(md5((module+":"+name).encode("ascii")).hexdigest(), 16)
    copyreg.add_extension(module, name, code & 0x7FFFFFFF)
