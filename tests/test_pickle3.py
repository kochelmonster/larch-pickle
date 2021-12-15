import io
import unittest
import pickle as opickle
import larch.pickle as pickle
import sys
import os
import copyreg
import platform
import builtins
import operator
import collections
from http.cookies import SimpleCookie
from test.support import TestFailed, _2G, _4G, bigmemtest, set_memlimit
try:
    from test.support.os_helper import TESTFN
except ImportError:
    from test.support import TESTFN


from pickle import bytes_types

# Tests that try a number of pickle protocols should have a
#     for proto in protocols:
# kind of outer loop.
protocols = [3, 4]

character_size = 4 if sys.maxunicode > 0xFFFF else 2


if platform.architecture()[0] == '64bit':
    set_memlimit("4G")


secure_unpickle = pickle.secure_unpickle


class UnseekableIO(io.BytesIO):
    def peek(self, *args):
        raise NotImplementedError

    def seekable(self):
        return False

    def seek(self, *args):
        raise io.UnsupportedOperation

    def tell(self):
        raise io.UnsupportedOperation


# We can't very well test the extension registry without putting known stuff
# in it, but we have to be careful to restore its original state.  Code
# should do this:
#
#     e = ExtensionSaver(extension_code)
#     try:
#         fiddle w/ the extension registry's stuff for extension_code
#     finally:
#         e.restore()

class ExtensionSaver:
    # Remember current registration for code (if any), and remove it (if
    # there is one).
    def __init__(self, code):
        self.code = code
        if code in copyreg._inverted_registry:
            self.pair = copyreg._inverted_registry[code]
            copyreg.remove_extension(self.pair[0], self.pair[1], code)
        else:
            self.pair = None

    # Restore previous registration for code.
    def restore(self):
        code = self.code
        curpair = copyreg._inverted_registry.get(code)
        if curpair is not None:
            copyreg.remove_extension(curpair[0], curpair[1], code)
        pair = self.pair
        if pair is not None:
            copyreg.add_extension(pair[0], pair[1], code)


@secure_unpickle
class C:
    def __eq__(self, other):
        return self.__dict__ == other.__dict__


@secure_unpickle
class D(C):
    def __init__(self, arg):
        pass


@secure_unpickle
class E(C):
    def __getinitargs__(self):
        return ()

import __main__
__main__.C = C
C.__module__ = "__main__"
__main__.D = D
D.__module__ = "__main__"
__main__.E = E
E.__module__ = "__main__"


@secure_unpickle
class myint(int):
    def __init__(self, x):
        self.str = str(x)


@secure_unpickle
class initarg(C):

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __getinitargs__(self):
        return self.a, self.b


@secure_unpickle
class metaclass(type):
    pass


@secure_unpickle
class use_metaclass(object, metaclass=metaclass):
    pass


@secure_unpickle
class pickling_metaclass(type):
    def __eq__(self, other):
        return (type(self) == type(other)
                and self.reduce_args == other.reduce_args)

    def __reduce__(self):
        return (create_dynamic_class, self.reduce_args)


@secure_unpickle
def create_dynamic_class(name, bases):
    result = pickling_metaclass(name, bases, dict())
    result.reduce_args = (name, bases)
    return result

# set([1,2]) pickled from 2.x
DATA3 = (b'\xd4\x00\x02\xd4\x03\xd4\x05\xab__builtin__\xa3set\x91\xd5\x02\x01\x02\xc0\xc7\x00\t\xc7\x00\t')

# xrange(5) pickled from 2.x with protocol 2
DATA4 = (b'\xd4\x00\x02\xd4\x03\xd4\x05\xab__builtin__\xa6xrange\x93\x00\x05\x01\xc0\xc7\x00\t\xc7\x00\t')

# a SimpleCookie() object pickled from 2.x with protocol 2
DATA5 = (b'\xd4\x00\x02\xd4\x04\x91\xd4\x05\xa6Cookie\xc4\x0cSimpleCookie\x80\xc7\x00\t\xc4\x03key\xd4\x04\x91\xd4\x05\xc1\x00\x00\x00\x03\xc4\x06Morsel\x83\xc4\x0bcoded_value\xc4\x05value\xc4\x05value\xc4\x05value\xc4\x03key\xc4\x03key\xc7\x00\t\xc4\x07comment\xc4\x00\xc4\x06domain\xc4\x00\xc4\x06secure\xc4\x00\xc4\x07expires\xc4\x00\xa7max-age\xc4\x00\xc4\x07version\xc4\x00\xc4\x04path\xc4\x00\xc4\x08httponly\xc4\x00\xc7\x00\t\xc7\x00\t')


def create_data():
    c = C()
    c.foo = 1
    c.bar = 2
    x = [0, 1, 2.0, 3.0+0j]
    # Append some integer test cases at cPickle.c's internal size
    # cutoffs.
    uint1max = 0xff
    uint2max = 0xffff
    int4max = 0x7fffffff
    x.extend([1, -1,
              uint1max, -uint1max, -uint1max-1,
              uint2max, -uint2max, -uint2max-1,
              int4max,  -int4max,  -int4max-1])
    y = ('abc', 'abc', c, c)
    x.append(y)
    x.append(y)
    x.append(5)
    return x


with open(os.path.join(os.path.dirname(__file__), "test.data"), "rb") as f:
    big_data = opickle.load(f, encoding="utf8")


@secure_unpickle
class Verb(object):
    __slots__ = ("obj", "method", "kwargs")

    def __init__(self, obj, method, **kwargs):
        self.obj = obj
        self.method = method
        self.kwargs = kwargs


@secure_unpickle
class _Neg(object):
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __getstate__(self):
        return self.value

    def __setstate__(self, state):
        self.value = state

    def __repr__(self):
        return "-{}".format(self.value)

    def __eq__(self, other):
        return self.value == other.value


class AbstractDataPickleTests(object):
    def test_pickle_impossible(self):
        objects = [
            iter(()),
            iter([]),
            (i for i in [1])]
        for o in objects:
            self.assertRaises(pickle.PicklingError, self.dumps, o)

    def test_slot_object(self):
        x = Verb("service_id", "add", a=1, b=2)
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x.obj, y.obj)
        self.assertEqual(x.method, y.method)
        self.assertEqual(x.kwargs, y.kwargs)

        x = Verb("service_id", "handle", sequence=iter([1, 2, 3]))
        self.assertRaises(pickle.PicklingError, self.dumps, x)

        x = Verb("service_id", "handle", sequence=[1, 2, 3])
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x.obj, y.obj)
        self.assertEqual(x.method, y.method)
        self.assertEqual(x.kwargs, y.kwargs)

    def test_slot_with_getstate(self):
        x = [[b'\xe5\xb5\xbbO\xf0|\xaaQpMz\xb4', None,
              (_Neg((4, b'\xe5\xb5\xbbO\xf0|\xaaQpMz\xb4')),)]]
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

    def test_big_data(self):
        global big_data
        s = self.dumps(big_data)
        d = self.loads(s)
        self.assertEqual(big_data, d)
        self.check_refcount()


class AbstractAttackPickleTests(object):
    # bytes, unicode and long are robust because is PyBytes_FromStringAndSize

    def test_attack_list(self):
        # test dos attack against list
        s = bytes([0xc9, 0xFF, 0xFF, 0xFF, 0xFF, 0])
        self.assertRaises(EOFError, self.loads, s)

        # test a save operation
        x = range(0x10000)
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

    def test_attack_tuple(self):
        # test dos attack against tuple
        s = bytes([0xdd, 0xFF, 0xFF, 0xFF, 0xFF])
        self.assertRaises(EOFError, self.loads, s)

        # test a save operation
        x = tuple(range(0x10000))
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

    def test_pickle_security(self):
        unsecure = """breakpoint compile delattr eval exec exit input locals
        globals memoryview open print quit setattr staticmethod classmethod
        super vars"""
        for s in unsecure.split():
            x = self.dumps(getattr(builtins, s))
            self.assertRaises(pickle.SecurityError, self.loads, x)

        unsecure = "methodcaller delitem setitem"
        for s in unsecure.split():
            x = self.dumps(getattr(operator, s))
            self.assertRaises(pickle.SecurityError, self.loads, x)


class AbstractPickleTests(object):
    # Subclass must define self.dumps, self.loads.

    _testdata = create_data()

    def setUp(self):
        pass

    def test_modules(self):
        objects = (len, operator.add, collections.OrderedDict())
        for o in objects:
            x = self.dumps(o)
            y = self.loads(x)
            self.assertEqual(o, y)

    def test_misc(self):
        # test various datatypes not tested by testdata
        for proto in protocols:
            x = myint(4)
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)

            x = (1, ())
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)

            x = initarg(1, x)
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)

        # XXX test __reduce__ protocol?

    def test_roundtrip_equality(self):
        expected = self._testdata
        for proto in protocols:
            s = self.dumps(expected, proto)
            got = self.loads(s)
            self.assertEqual(expected, got)

    def test_recursive_list(self):
        l = []
        l.append(l)
        for proto in protocols:
            s = self.dumps(l, proto)
            x = self.loads(s)
            self.assertEqual(len(x), 1)
            self.assertTrue(x is x[0])

    def test_recursive_tuple(self):
        t = ([],)
        t[0].append(t)
        for proto in protocols:
            s = self.dumps(t, proto)
            x = self.loads(s)
            self.assertEqual(len(x), 1)
            self.assertEqual(len(x[0]), 1)
            self.assertTrue(x is x[0][0])

    def test_recursive_dict(self):
        d = {}
        d[1] = d
        for proto in protocols:
            s = self.dumps(d, proto)
            x = self.loads(s)
            self.assertEqual(list(x.keys()), [1])
            self.assertTrue(x[1] is x)

    def test_recursive_inst(self):
        i = C()
        i.attr = i
        for proto in protocols:
            s = self.dumps(i, proto)
            x = self.loads(s)
            self.assertEqual(dir(x), dir(i))
            self.assertIs(x.attr, x)

    def test_recursive_multi(self):
        l = []
        d = {1:l}
        i = C()
        i.attr = d
        l.append(i)
        for proto in protocols:
            s = self.dumps(l, proto)
            x = self.loads(s)
            self.assertEqual(len(x), 1)
            self.assertEqual(dir(x[0]), dir(i))
            self.assertEqual(list(x[0].attr.keys()), [1])
            self.assertTrue(x[0].attr[1] is x)

    def test_unicode(self):
        endcases = ['', '<\\u>', '<\\\u1234>', '<\n>',
                    '<\\>', '<\\\U00012345>',
                    # surrogates
                    '<\udc80>']
        for proto in protocols:
            for u in endcases:
                p = self.dumps(u, proto)
                u2 = self.loads(p)
                self.assertEqual(u2, u)

    def test_unicode_high_plane(self):
        t = '\U00012345'
        for proto in protocols:
            p = self.dumps(t, proto)
            t2 = self.loads(p)
            self.assertEqual(t2, t)

    def test_bytes(self):
        for proto in protocols:
            for s in b'', b'xyz', b'xyz'*100:
                p = self.dumps(s, proto)
                self.assertEqual(self.loads(p), s)
            for s in [bytes([i]) for i in range(256)]:
                p = self.dumps(s, proto)
                self.assertEqual(self.loads(p), s)
            for s in [bytes([i, i]) for i in range(256)]:
                p = self.dumps(s, proto)
                self.assertEqual(self.loads(p), s)

    def test_ints(self):
        import sys
        for proto in protocols:
            n = sys.maxsize
            while n:
                for expected in (-n, n):
                    s = self.dumps(expected, proto)
                    n2 = self.loads(s)
                    self.assertEqual(expected, n2)
                n = n >> 1

    def test_long(self):
        for proto in protocols:
            # 256 bytes is where LONG4 begins.
            for nbits in 1, 8, 8*254, 8*255, 8*256, 8*257:
                nbase = 1 << nbits
                for npos in nbase-1, nbase, nbase+1:
                    for n in npos, -npos:
                        pickle = self.dumps(n, proto)
                        got = self.loads(pickle)
                        self.assertEqual(n, got)
        # Try a monster.  This is quadratic-time in protos 0 & 1, so don't
        # bother with those.
        nbase = int("deadbeeffeedface", 16)
        nbase += nbase << 1000000
        for n in nbase, -nbase:
            p = self.dumps(n, 2)
            got = self.loads(p)
            self.assertEqual(n, got)

    def test_float(self):
        test_values = [0.0, 4.94e-324, 1e-310, 7e-308, 6.626e-34, 0.1, 0.5,
                       3.14, 263.44582062374053, 6.022e23, 1e30]
        test_values = test_values + [-x for x in test_values]
        for proto in protocols:
            for value in test_values:
                pickle = self.dumps(value, proto)
                got = self.loads(pickle)
                self.assertEqual(value, got)

    def test_reduce(self):
        pass

    def test_getinitargs(self):
        pass

    def test_metaclass(self):
        a = use_metaclass()
        for proto in protocols:
            s = self.dumps(a, proto)
            b = self.loads(s)
            self.assertEqual(a.__class__, b.__class__)

    def test_dynamic_class(self):
        a = create_dynamic_class("my_dynamic_class", (object,))
        copyreg.pickle(pickling_metaclass, pickling_metaclass.__reduce__)
        for proto in protocols:
            s = self.dumps(a, proto)
            b = self.loads(s)
            self.assertEqual(a, b)

    def test_structseq(self):
        import time
        import os

        t = time.localtime()
        for proto in protocols:
            s = self.dumps(t, proto)
            u = self.loads(s)
            self.assertEqual(t, u)
            if hasattr(os, "stat"):
                t = os.stat(os.curdir)
                s = self.dumps(t, proto)
                u = self.loads(s)
                self.assertEqual(t, u)
            if hasattr(os, "statvfs"):
                t = os.statvfs(os.curdir)
                s = self.dumps(t, proto)
                u = self.loads(s)
                self.assertEqual(t, u)

    def test_long1(self):
        x = 12345678910111213141516178920
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)

    def test_long4(self):
        x = 12345678910111213141516178920 << (256*8)
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)

    def test_short_tuples(self):
        # Map (proto, len(tuple)) to expected opcode.
        a = ()
        b = (1,)
        c = (1, 2)
        d = (1, 2, 3)
        e = (1, 2, 3, 4)
        for proto in protocols:
            for x in a, b, c, d, e:
                s = self.dumps(x, proto)
                y = self.loads(s)
                self.assertEqual(x, y, (proto, x, s, y))

    def test_singletons(self):
        # Map (proto, singleton) to expected opcode.
        for proto in protocols:
            for x in None, False, True:
                s = self.dumps(x, proto)
                y = self.loads(s)
                self.assertTrue(x is y, (proto, x, s, y))

    def test_newobj_tuple(self):
        x = MyTuple([1, 2, 3])
        x.foo = 42
        x.bar = "hello"
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(tuple(x), tuple(y))
            self.assertEqual(x.__dict__, y.__dict__)

    def test_newobj_list(self):
        x = MyList([1, 2, 3])
        x.foo = 42
        x.bar = "hello"
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(list(x), list(y))
            self.assertEqual(x.__dict__, y.__dict__)

    def test_newobj_generic(self):
        for proto in protocols:
            for C in myclasses:
                B = C.__base__
                x = C(C.sample)
                x.foo = 42
                s = self.dumps(x, proto)
                y = self.loads(s)
                detail = (proto, C, B, x, y, type(y))
                self.assertEqual(B(x), B(y), detail)
                self.assertEqual(x.__dict__, y.__dict__, detail)

    # Register a type with copyreg, with extension code extcode.  Pickle
    # an object of that type.  Check that the resulting pickle uses opcode
    # (EXT[124]) under proto 2, and not in proto 1.

    def produce_global_ext(self, extcode):
        e = ExtensionSaver(extcode)
        try:
            copyreg.add_extension(__name__, "MyList", extcode)
            x = MyList([1, 2, 3])
            x.foo = 42
            x.bar = "hello"
            # Dump using protocol 2 for test.
            s2 = self.dumps(x, 2)
            self.assertNotIn(__name__.encode("utf-8"), s2)
            self.assertNotIn(b"MyList", s2)

            y = self.loads(s2)
            self.assertEqual(list(x), list(y))
            self.assertEqual(x.__dict__, y.__dict__)

        finally:
            e.restore()

    def test_global_ext1(self):
        self.produce_global_ext(0x00000001)  # smallest EXT1 code
        self.produce_global_ext(0x000000ff)  # largest EXT1 code

    def test_global_ext2(self):
        self.produce_global_ext(0x00000100)  # smallest EXT2 code
        self.produce_global_ext(0x0000ffff)  # largest EXT2 code
        self.produce_global_ext(0x0000abcd)  # check endianness

    def test_global_ext4(self):
        self.produce_global_ext(0x00010000)  # smallest EXT4 code
        self.produce_global_ext(0x7fffffff)  # largest EXT4 code
        self.produce_global_ext(0x12abcdef)  # check endianness

    def test_list_chunking(self):
        n = 10  # too small to chunk
        x = list(range(n))
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)

        n = 2500  # expect at least two chunks when proto > 0
        x = list(range(n))
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)

    def test_dict_chunking(self):
        n = 10  # too small to chunk
        x = dict.fromkeys(range(n))
        for proto in protocols:
            s = self.dumps(x, proto)
            self.assertIsInstance(s, bytes_types)
            y = self.loads(s)
            self.assertEqual(x, y)

        n = 2500  # expect at least two chunks when proto > 0
        x = dict.fromkeys(range(n))
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(x, y)

    def test_simple_newobj(self):
        x = object.__new__(SimpleNewObj)  # avoid __init__
        x.abc = 666
        for proto in protocols:
            s = self.dumps(x, proto)
            y = self.loads(s)   # will raise TypeError if __init__ called
            self.assertEqual(y.abc, 666)
            self.assertEqual(x.__dict__, y.__dict__)

    def test_newobj_list_slots(self):
        x = SlotList([1, 2, 3])
        x.foo = 42
        x.bar = "hello"
        s = self.dumps(x, 2)
        y = self.loads(s)
        self.assertEqual(list(x), list(y))
        self.assertEqual(x.__dict__, y.__dict__)
        self.assertEqual(x.foo, y.foo)
        self.assertEqual(x.bar, y.bar)

    def test_reduce_overrides_default_reduce_ex(self):
        for proto in protocols:
            x = REX_one()
            self.assertEqual(x._reduce_called, 0)
            s = self.dumps(x, proto)
            self.assertEqual(x._reduce_called, 1)
            y = self.loads(s)
            self.assertEqual(y._reduce_called, 0)

    def test_reduce_ex_called(self):
        for proto in protocols:
            x = REX_two()
            self.assertEqual(x._proto, None)
            s = self.dumps(x, proto)
            self.assertEqual(x._proto, 4)
            y = self.loads(s)
            self.assertEqual(y._proto, None)

    def test_reduce_ex_overrides_reduce(self):
        for proto in protocols:
            x = REX_three()
            self.assertEqual(x._proto, None)
            s = self.dumps(x, proto)
            self.assertEqual(x._proto, 4)
            y = self.loads(s)
            self.assertEqual(y._proto, None)

    def test_reduce_ex_calls_base(self):
        for proto in protocols:
            x = REX_four()
            self.assertEqual(x._proto, None)
            s = self.dumps(x, proto)
            self.assertEqual(x._proto, 4)
            y = self.loads(s)
            self.assertEqual(y._proto, 4)

    def test_reduce_calls_base(self):
        for proto in protocols:
            x = REX_five()
            self.assertEqual(x._reduce_called, 0)
            s = self.dumps(x, proto)
            self.assertEqual(x._reduce_called, 1)
            y = self.loads(s)
            self.assertEqual(y._reduce_called, 1)

    def test_reduce_sequence(self):
        for proto in protocols:
            x = REX_six([1, 2, 3])
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(y.items, [1, 2, 3])

    def test_reduce_dict(self):
        d = {1: -1, 2: -2, 3: -3}
        for proto in protocols:
            x = REX_seven(d)
            s = self.dumps(x, proto)
            y = self.loads(s)
            self.assertEqual(y.table, d)

    def test_reduce_bad_iterator(self):
        # Issue4176: crash when 4th and 5th items of __reduce__()
        # are not iterators
        class C(object):
            def __reduce__(self):
                # 4th item is not an iterator
                return list, (), None, [], None
        class D(object):
            def __reduce__(self):
                # 5th item is not an iterator
                return dict, (), None, None, []

        # Protocol 0 is less strict and also accept iterables.
        for proto in protocols:
            try:
                self.dumps(C(), proto)
            except (pickle.PickleError):
                pass
            try:
                self.dumps(D(), proto)
            except (pickle.PickleError):
                pass

    def test_many_puts_and_gets(self):
        # Test that internal data structures correctly deal with lots of
        # puts/gets.
        keys = ("aaa" + str(i) for i in range(100))
        large_dict = dict((k, [4, 5, 6]) for k in keys)
        obj = [dict(large_dict), dict(large_dict), dict(large_dict)]

        for proto in protocols:
            dumped = self.dumps(obj, proto)
            loaded = self.loads(dumped)
            self.assertEqual(loaded, obj,
                             "Failed protocol %d: %r != %r"
                             % (proto, obj, loaded))

    def test_attribute_name_interning(self):
        # Test that attribute names of pickled objects are interned when
        # unpickling.
        for proto in protocols:
            x = C()
            x.foo = 42
            x.bar = "hello"
            s = self.dumps(x, proto)
            y = self.loads(s)
            x_keys = sorted(x.__dict__)
            y_keys = sorted(y.__dict__)
            for x_key, y_key in zip(x_keys, y_keys):
                self.assertIs(x_key, y_key)

    def test_unpickle_from_2x(self):
        # Unpickle non-trivial data from Python 2.x.
        loaded = self.loads(DATA3)
        self.assertEqual(loaded, set([1, 2]))
        loaded = self.loads(DATA4)
        self.assertEqual(type(loaded), type(range(0)))
        self.assertEqual(list(loaded), list(range(5)))

        loaded = self.loads(DATA5)
        self.assertEqual(type(loaded), SimpleCookie)
        self.assertEqual(list(loaded.keys()), ["key"])
        self.assertEqual(loaded["key"].value, "value")

    def test_large_pickles(self):
        # Test the correctness of internal buffering routines when handling
        # large data.
        for proto in protocols:
            data = (1, min, b'xy' * (30 * 1024), len)
            dumped = self.dumps(data, proto)
            loaded = self.loads(dumped)
            self.assertEqual(len(loaded), len(data))
            self.assertEqual(loaded, data)

    def test_refcount_bug(self):
        # was only reproducable with larch.reactive
        try:
            from larch.reactive import SELF, Pointer, PointerExpression, _ExpressionOperandRoot
        except ImportError:
            return

        secure_unpickle(Pointer)
        secure_unpickle(PointerExpression)
        secure_unpickle(_ExpressionOperandRoot)
        t = (" " + SELF._docid, SELF.firstname + " ")
        x = self.dumps(t, proto=3)
        y = self.loads(x)
        self.assertEqual(repr(t), repr(y))


class BigmemPickleTests(object):

    # Binary protocols can serialize longs of up to 2GB-1

    @bigmemtest(size=_2G, memuse=1 + 1, dry_run=False)
    def test_huge_long_32b(self, size):
        data = 1 << (8 * size)
        try:
            for proto in protocols:
                if proto < 2:
                    continue
                with self.assertRaises((ValueError, OverflowError)):
                    self.dumps(data, proto=proto)
        finally:
            data = None

    # Protocol 3 can serialize up to 4GB-1 as a bytes object
    # (older protocols don't have a dedicated opcode for bytes and are
    # too inefficient)

    @bigmemtest(size=_2G, memuse=1 + 1, dry_run=False)
    def test_huge_bytes_32b(self, size):
        data = b"abcd" * (size // 4)
        try:
            for proto in protocols:
                if proto < 3:
                    continue
                try:
                    pickled = self.dumps(data, proto=proto)
                    self.assertTrue(b"abcd" in pickled[:15])
                    self.assertTrue(b"abcd" in pickled[-15:])
                finally:
                    pickled = None
        finally:
            data = None

    @bigmemtest(size=_4G, memuse=1 + 1, dry_run=False)
    def test_huge_bytes_64b(self, size):
        data = b"a" * size
        try:
            for proto in protocols:
                if proto < 3:
                    continue
                with self.assertRaises((ValueError, OverflowError)):
                    self.dumps(data, proto=proto)
        finally:
            data = None

    # All protocols use 1-byte per printable ASCII character; we add another
    # byte because the encoded form has to be copied into the internal buffer.

    @bigmemtest(size=_2G, memuse=2 + character_size, dry_run=False)
    def test_huge_str_32b(self, size):
        data = "abcd" * (size // 4)
        try:
            for proto in protocols:
                try:
                    pickled = self.dumps(data, proto=proto)
                    self.assertTrue(b"abcd" in pickled[:15])
                    self.assertTrue(b"abcd" in pickled[-15:])
                finally:
                    pickled = None
        finally:
            data = None

    # BINUNICODE (protocols 1, 2 and 3) cannot carry more than
    # 2**32 - 1 bytes of utf-8 encoded unicode.

    @bigmemtest(size=_4G, memuse=1 + character_size, dry_run=False)
    def test_huge_str_64b(self, size):
        data = "a" * size
        try:
            for proto in protocols:
                if proto == 0:
                    continue
                with self.assertRaises((ValueError, OverflowError)):
                    self.dumps(data, protocol=proto)
        finally:
            data = None


# Test classes for reduce_ex
@secure_unpickle
class REX_one(object):
    _reduce_called = 0

    def __reduce__(self):
        self._reduce_called = 1
        return REX_one, ()
    # No __reduce_ex__ here, but inheriting it from object


@secure_unpickle
class REX_two(object):
    _proto = None

    def __reduce_ex__(self, proto):
        self._proto = proto
        return REX_two, ()
    # No __reduce__ here, but inheriting it from object


@secure_unpickle
class REX_three(object):
    _proto = None

    def __reduce_ex__(self, proto):
        self._proto = proto
        return REX_two, ()

    def __reduce__(self):
        raise TestFailed("This __reduce__ shouldn't be called")


@secure_unpickle
class REX_four(object):
    _proto = None

    def __reduce_ex__(self, proto):
        self._proto = proto
        return object.__reduce_ex__(self, proto)
    # Calling base class method should succeed


@secure_unpickle
class REX_five(object):
    _reduce_called = 0

    def __reduce__(self):
        self._reduce_called = 1
        return object.__reduce__(self)
    # This one used to fail with infinite recursion


@secure_unpickle
class REX_six(object):
    """This class is used to check the 4th argument (list iterator) of
    the reduce protocol.
    """

    def __init__(self, items=None):
        self.items = items if items is not None else []

    def __eq__(self, other):
        return type(self) is type(other) and self.items == other.items

    def append(self, item):
        self.items.append(item)

    def __reduce__(self):
        return type(self), (), None, iter(self.items), None


@secure_unpickle
class REX_seven(object):
    """This class is used to check the 5th argument (dict iterator) of
    the reduce protocol.
    """

    def __init__(self, table=None):
        self.table = table if table is not None else {}

    def __eq__(self, other):
        return type(self) is type(other) and self.table == other.table

    def __setitem__(self, key, value):
        self.table[key] = value

    def __reduce__(self):
        return type(self), (), None, None, iter(self.table.items())


# Test classes for newobj

@secure_unpickle
class MyInt(int):
    sample = 1


@secure_unpickle
class MyFloat(float):
    sample = 1.0


@secure_unpickle
class MyComplex(complex):
    sample = 1.0 + 0.0j


@secure_unpickle
class MyStr(str):
    sample = "hello"


@secure_unpickle
class MyUnicode(str):
    sample = "hello \u1234"


@secure_unpickle
class MyTuple(tuple):
    sample = (1, 2, 3)


@secure_unpickle
class MyList(list):
    sample = [1, 2, 3]


@secure_unpickle
class MyDict(dict):
    sample = {"a": 1, "b": 2}


myclasses = [MyInt, MyFloat,
             MyComplex,
             MyStr, MyUnicode,
             MyTuple, MyList, MyDict]


@secure_unpickle
class SlotList(MyList):
    __slots__ = ["foo"]


@secure_unpickle
class SimpleNewObj(object):
    def __init__(self, a, b, c):
        # raise an error, to make sure this isn't called
        raise TypeError("SimpleNewObj.__init__() didn't expect to get called")


@secure_unpickle
class BadGetattr:
    def __getattr__(self, key):
        self.foo


class AbstractPickleModuleTests(object):

    def test_dump_closed_file(self):
        import os
        f = open(TESTFN, "wb")
        try:
            f.close()
            self.assertRaises(ValueError, pickle.dump, 123, f)
        finally:
            os.remove(TESTFN)

    def test_load_closed_file(self):
        import os
        f = open(TESTFN, "wb")
        try:
            f.close()
            self.assertRaises(ValueError, pickle.dump, 123, f)
        finally:
            os.remove(TESTFN)

    def test_load_from_and_dump_to_file(self):
        stream = io.BytesIO()
        data = [123, {}, 124]
        pickle.dump(data, stream)
        stream.seek(0)
        unpickled = pickle.load(stream)
        self.assertEqual(unpickled, data)

    def test_callapi(self):
        f = io.BytesIO()
        # With and without keyword arguments
        pickle.dump(123, f, -1)
        pickle.dump(123, file=f, protocol=-1)
        pickle.dumps(123, -1)
        pickle.dumps(123, protocol=-1)
        pickle.Pickler(f, -1)
        pickle.Pickler(f, protocol=-1)

    def test_bad_init(self):
        # Test issue3664 (pickle can segfault from a badly initialized Pickler).
        # Override initialization without calling __init__() of the superclass.
        class BadPickler(pickle.Pickler):
            def __init__(self): pass

        class BadUnpickler(pickle.Unpickler):
            def __init__(self): pass

        self.assertRaises(pickle.PicklingError, BadPickler().dump, 0)
        self.assertRaises(pickle.UnpicklingError, BadUnpickler().load)

    def test_bad_input(self):
        s = bytes([0xd4])
        self.assertRaises(EOFError, pickle.loads, s)


class AbstractPicklerUnpicklerObjectTests(object):

    pickler_class = None
    unpickler_class = None

    def setUp(self):
        assert self.pickler_class
        assert self.unpickler_class

    def test_reusing_unpickler_objects(self):
        data1 = ["abcdefg", "abcdefg", 44]
        f = io.BytesIO()
        pickler = self.pickler_class(f)
        pickler.dump(data1)
        pickled1 = f.getvalue()

        data2 = ["abcdefg", 44, 44]
        f = io.BytesIO()
        pickler = self.pickler_class(f)
        pickler.dump(data2)
        pickled2 = f.getvalue()

        f = io.BytesIO()
        f.write(pickled1)
        f.seek(0)
        unpickler = self.unpickler_class(f)
        self.assertEqual(unpickler.load(), data1)

        f.seek(0)
        f.truncate()
        f.write(pickled2)
        f.seek(0)
        self.assertEqual(unpickler.load(), data2)

    def _check_multiple_unpicklings(self, ioclass):
        for proto in protocols:
            data1 = [(x, str(x)) for x in range(2000)] + [b"abcde", len]
            f = ioclass()
            pickler = self.pickler_class(f, protocol=proto)
            pickler.dump(data1)
            pickled = f.getvalue()

            N = 5
            f = ioclass(pickled * N)
            unpickler = self.unpickler_class(f)
            for i in range(N):
                if f.seekable():
                    pos = f.tell()
                self.assertEqual(unpickler.load(), data1)
                if f.seekable():
                    self.assertEqual(f.tell(), pos + len(pickled))
            self.assertRaises(EOFError, unpickler.load)

    def test_multiple_unpicklings_seekable(self):
        self._check_multiple_unpicklings(io.BytesIO)

    def test_multiple_unpicklings_unseekable(self):
        self._check_multiple_unpicklings(UnseekableIO)

    def test_unpickling_buffering_readline(self):
        # Issue #12687: the unpickler's buffering logic could fail with
        # text mode opcodes.
        data = list(range(10))
        for proto in protocols:
            for buf_size in range(1, 11):
                f = io.BufferedRandom(io.BytesIO(), buffer_size=buf_size)
                pickler = self.pickler_class(f, protocol=proto)
                pickler.dump(data)
                f.seek(0)
                unpickler = self.unpickler_class(f)
                self.assertEqual(unpickler.load(), data)


class PickleTests(
        AbstractDataPickleTests,
        AbstractPickleTests, AbstractPickleModuleTests,
        AbstractAttackPickleTests, BigmemPickleTests,
        unittest.TestCase):

    def setUp(self):
        super(PickleTests, self).setUp()
        self._pickler = pickle.Pickler()
        self._unpickler = pickle.Unpickler(secure=True)
        self._dumps = self._pickler.dumps
        self._loads = self._unpickler.loads

    def check_refcount(self):
        self.assertEqual(
            self._pickler.last_refcount, self._unpickler.last_refcount)

    def dumps(self, arg, proto=4, fast=0):
        if proto != 4:
            return pickle.dumps(arg, protocol=proto)
        else:
            return self._dumps(arg)

    def loads(self, buf):
        return self._loads(buf)

    module = pickle
    error = KeyError


class FilePicklerTests(unittest.TestCase, AbstractPickleTests):
    error = KeyError

    def dumps(self, arg, proto=0, fast=0):
        f = io.BytesIO()
        p = pickle.Pickler(f, protocol=proto)
        p.dump(arg)
        f.seek(0)
        return f.read()

    def loads(self, buf):
        f = io.BytesIO(buf)
        u = pickle.Unpickler(f)
        return u.load()


class PicklerUnpicklerObjectTests(
        unittest.TestCase, AbstractPicklerUnpicklerObjectTests):
    pickler_class = pickle.Pickler
    unpickler_class = pickle.Unpickler


class TestLarchBugs(unittest.TestCase):
    def test_bug(self):
        s = pickle.dumps(["four", "two", "four"])
        unpickler = pickle.Unpickler()
        r1 = unpickler.loads(s)  # all ok
        unpickler.loads(b'\xd4\x00\x03\x01')  # protocol 3
        r2 = unpickler.loads(s)  # switch back to 4
        self.assertEqual(r1, r2)


if __name__ == "__main__":
    unittest.main()
