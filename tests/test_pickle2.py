import unittest
import larch.pickle as pickle
import io
import sys
import copy_reg
import cPickle
from Cookie import SimpleCookie

class TestFailed(Exception):
    """Test failed."""

TESTFN = "tmp.test"


# Copy of test.test_support.run_with_locale. This is needed to support Python
# 2.4, which didn't include it. This is all to support test_xpickle, which
# bounces pickled objects through older Python versions to test backwards
# compatibility.
def run_with_locale(catstr, *locales):
    def decorator(func):
        def inner(*args, **kwds):
            try:
                import locale
                category = getattr(locale, catstr)
                orig_locale = locale.setlocale(category)
            except AttributeError:
                # if the test author gives us an invalid category string
                raise
            except:
                # cannot retrieve original locale, so do nothing
                locale = orig_locale = None
            else:
                for loc in locales:
                    try:
                        locale.setlocale(category, loc)
                        break
                    except:
                        pass

            # now run the function, resetting the locale on exceptions
            try:
                return func(*args, **kwds)
            finally:
                if locale and orig_locale:
                    locale.setlocale(category, orig_locale)
        inner.func_name = func.func_name
        inner.__doc__ = func.__doc__
        return inner
    return decorator


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
        if code in copy_reg._inverted_registry:
            self.pair = copy_reg._inverted_registry[code]
            copy_reg.remove_extension(self.pair[0], self.pair[1], code)
        else:
            self.pair = None

    # Restore previous registration for code.
    def restore(self):
        code = self.code
        curpair = copy_reg._inverted_registry.get(code)
        if curpair is not None:
            copy_reg.remove_extension(curpair[0], curpair[1], code)
        pair = self.pair
        if pair is not None:
            copy_reg.add_extension(pair[0], pair[1], code)

class C:
    def __cmp__(self, other):
        return cmp(self.__dict__, other.__dict__)

class CN(object):
    def __cmp__(self, other):
        return cmp(self.__dict__, other.__dict__)

import __main__
__main__.C = C
C.__module__ = "__main__"

class myint(int):
    def __init__(self, x):
        self.str = str(x)

class initarg(C):

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __getinitargs__(self):
        return self.a, self.b

class metaclass(type):
    pass

class use_metaclass(object):
    __metaclass__ = metaclass

class pickling_metaclass(type):
    def __eq__(self, other):
        return (type(self) == type(other) and
                self.reduce_args == other.reduce_args)

    def __reduce__(self):
        return (create_dynamic_class, self.reduce_args)

    __hash__ = None

def create_dynamic_class(name, bases):
    result = pickling_metaclass(name, bases, dict())
    result.reduce_args = (name, bases)
    return result

# set([1,2]) pickled from 3.x with protocol 2
DATA3 = b'\xd4\x00\x02\xd4\x03\xd4\x05\xc4\x0b__builtin__\xa3set\x91\xd5\x02\x01\x02\xc0\xc7\x00\t\xc7\x00\t'

# range(5) pickled from 3.x with protocol 2
DATA4 = b'\xd4\x00\x02\xd4\x03\xd4\x05\xc4\x0b__builtin__\xc4\x06xrange\x93\x00\x05\x01\xc0\xc7\x00\t\xc7\x00\t'

# a SimpleCookie() object pickled from 3.x with protocol 2
DATA5 = b'\xd4\x00\x02\xd4\x04\x91\xd4\x05\xc4\x06Cookie\xc4\x0cSimpleCookie\xc0\xc7\x00\t\xc4\x03key\xd4\x04\x91\xd4\x05\xc1\x00\x00\x00\x03\xc4\x06Morsel\x83\xc4\x03key\xc4\x03key\xc4\x0bcoded_value\xc4\x05value\xc4\x05value\xc4\x05value\xc7\x00\t\xa7max-age\xc4\x00\xc4\x07comment\xc4\x00\xc4\x07expires\xc4\x00\xc4\x08httponly\xc4\x00\xc4\x07version\xc4\x00\xc4\x06secure\xc4\x00\xc4\x06domain\xc4\x00\xc4\x04path\xc4\x00\xc7\x00\t\xc7\x00\t'


def create_data():
    c = C()
    c.foo = 1
    c.bar = 2
    x = [0, 1L, 2.0, 3.0+0j]
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

with open("test.data", "rb") as f:
    big_data = cPickle.load(f)


class Verb(object):
    __slots__ = ("obj", "method", "kwargs")

    def __init__(self, obj, method, **kwargs):
        self.obj = obj
        self.method = method
        self.kwargs = kwargs


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
        x = [['\xe5\xb5\xbbO\xf0|\xaaQpMz\xb4', None, 
              (_Neg((4, '\xe5\xb5\xbbO\xf0|\xaaQpMz\xb4')),)]]
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
        s = "".join(map(chr, [0xc9, 0xFF, 0xFF, 0xFF, 0xFF, 0]))
        self.assertRaises(EOFError, self.loads, s)
        
        # test a save operation
        x = range(0x10000)
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

    def test_attack_tuple(self):
        # test dos attack against tuple
        s = "".join(map(chr, [0xdd, 0xFF, 0xFF, 0xFF, 0xFF]))
        self.assertRaises(EOFError, self.loads, s)

        # test a save operation
        x = tuple(range(0x10000))
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

    def test_attack_wrong_ext(self):
        for i in range(13, 0x100):
            s = "".join(map(chr, [0xd4, i, 0]))
            self.assertRaises(
                (pickle.UnpicklingError, TypeError), self.loads, s)
        

class AbstractPickleTests(object):
    # Subclass must define self.dumps, self.loads, self.error.

    _testdata = create_data()

    def setUp(self):
        pass

    def test_refcount(self):
        data = [
            "abcdefghijklmnopqrstuvwxyz"*10, 
            u"abcdefghijklmnopqrstuvwxyz"*10, 
            {"a":1},
            [ 1, 2, 3, 4, 5, 6, 7 ],
            ( 1, 2, 3, 4, 5, 6, 7 ),
            0xFFFFFFFFFFFFFFFFFFFF,
            0xFFFFF,
            C(),
            111111.111 ]

        data = data[:1]
        for x in data:
            s = self.dumps(x)
            y = self.loads(s)
            self.assertEqual(x, y)
            self.assertEqual(sys.getrefcount(y), 2)

    def test_misc(self):
        # test various datatypes not tested by testdata
        x = myint(4)
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

        x = (1, ())
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

        x = initarg(1, x)
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

        # XXX test __reduce__ protocol?

    def test_roundtrip_equality(self):
        expected = self._testdata
        s = self.dumps(expected)
        got = self.loads(s)
        self.assertEqual(expected, got)

    def test_recursive_list(self):
        l = []
        l.append(l)
        s = self.dumps(l)
        x = self.loads(s)
        self.assertEqual(len(x), 1)
        self.assertTrue(x is x[0])

    def test_recursive_tuple(self):
        t = ([],)
        t[0].append(t)
        s = self.dumps(t)
        x = self.loads(s)
        self.assertEqual(len(x), 1)
        self.assertEqual(len(x[0]), 1)
        self.assertTrue(x is x[0][0])

    def test_recursive_dict(self):
        d = {}
        d[1] = d
        s = self.dumps(d)
        x = self.loads(s)
        self.assertEqual(x.keys(), [1])
        self.assertTrue(x[1] is x)

    def test_recursive_inst(self):
        i = C()
        i.attr = i
        s = self.dumps(i)
        x = self.loads(s)
        self.assertEqual(dir(x), dir(i))
        self.assertTrue(x.attr is x)

    def test_recursive_inst_new_style(self):
        i = CN()
        i.attr = i
        s = self.dumps(i)
        x = self.loads(s)
        self.assertEqual(dir(x), dir(i))
        self.assertTrue(x.attr is x)

    def test_recursive_multi(self):
        l = []
        d = {1:l}
        i = C()
        i.attr = d
        l.append(i)
        s = self.dumps(l)
        x = self.loads(s)
        self.assertEqual(len(x), 1)
        self.assertEqual(dir(x[0]), dir(i))
        self.assertEqual(x[0].attr.keys(), [1])
        self.assertTrue(x[0].attr[1] is x)

    def test_unicode(self):
        endcases = [u'', u'<\\u>', u'<\\\u1234>', u'<\n>',
                    u'<\\>', u'<\\\U00012345>']
        for u in endcases:
            p = self.dumps(u)
            u2 = self.loads(p)
            self.assertEqual(u2, u)

    def test_unicode_high_plane(self):
        t = u'\U00012345'
        p = self.dumps(t)
        t2 = self.loads(p)
        self.assertEqual(t2, t)

    def test_ints(self):
        import sys
        n = sys.maxint
        while n:
            for expected in (-n, n):
                s = self.dumps(expected)
                n2 = self.loads(s)
                self.assertEqual(expected, n2)
            n = n >> 1

    def test_maxint64(self):
        maxint64 = (1L << 63) - 1
        got = self.loads(self.dumps(maxint64))
        self.assertEqual(got, maxint64)

    def test_long(self):
        # 256 bytes is where LONG4 begins.
        for nbits in 1, 8, 8*254, 8*255, 8*256, 8*257:
            nbase = 1L << nbits
            for npos in nbase-1, nbase, nbase+1:
                for n in npos, -npos:
                    pickle = self.dumps(n)
                    got = self.loads(pickle)
                    self.assertEqual(n, got)
        # Try a monster.  This is quadratic-time in protos 0 & 1, so don't
        # bother with those.
        nbase = long("deadbeeffeedface", 16)
        nbase += nbase << 1000000
        for n in nbase, -nbase:
            p = self.dumps(n, 2)
            got = self.loads(p)
            self.assertEqual(n, got)

    def test_float(self):
        test_values = [0.0, 4.94e-324, 1e-310, 7e-308, 6.626e-34, 0.1, 0.5,
                       3.14, 263.44582062374053, 6.022e23, 1e30]
        test_values = test_values + [-x for x in test_values]
        for value in test_values:
            pickle = self.dumps(value)
            got = self.loads(pickle)
            self.assertEqual(value, got)

    def test_metaclass(self):
        a = use_metaclass()
        s = self.dumps(a)
        b = self.loads(s)
        self.assertEqual(a.__class__, b.__class__)

    def test_dynamic_class(self):
        a = create_dynamic_class("my_dynamic_class", (object,))
        copy_reg.pickle(pickling_metaclass, pickling_metaclass.__reduce__)
        s = self.dumps(a)
        b = self.loads(s)
        self.assertEqual(a, b)

    def test_structseq(self):
        import time
        import os

        t = time.localtime()
        s = self.dumps(t)
        u = self.loads(s)
        self.assertEqual(t, u)
        if hasattr(os, "stat"):
            t = os.stat(os.curdir)
            s = self.dumps(t)
            u = self.loads(s)
            self.assertEqual(t, u)
        if hasattr(os, "statvfs"):
            t = os.statvfs(os.curdir)
            s = self.dumps(t)
            u = self.loads(s)
            self.assertEqual(t, u)

    def test_long1(self):
        x = 12345678910111213141516178920L
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

    def test_long4(self):
        x = 12345678910111213141516178920L << (256*8)
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)
        
    def test_short_tuples(self):
        # Map (proto, len(tuple)) to expected opcode.
        a = ()
        b = (1,)
        c = (1, 2)
        d = (1, 2, 3)
        e = (1, 2, 3, 4)
        for x in a, b, c, d, e:
            s = self.dumps(x)
            y = self.loads(s)
            self.assertEqual(x, y)

    def test_singletons(self):
        # Map (proto, singleton) to expected opcode.
        for x in None, False, True:
            s = self.dumps(x)
            y = self.loads(s)
            self.assertTrue(x is y)

    def test_newobj_tuple(self):
        x = MyTuple([1, 2, 3])
        x.foo = 42
        x.bar = "hello"
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(tuple(x), tuple(y))
        self.assertEqual(x.__dict__, y.__dict__)

    def test_newobj_list(self):
        x = MyList([1, 2, 3])
        x.foo = 42
        x.bar = "hello"
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(list(x), list(y))
        self.assertEqual(x.__dict__, y.__dict__)

    def test_newobj_generic(self):
        for C in myclasses:
            B = C.__base__
            x = C(C.sample)
            x.foo = 42
            s = self.dumps(x)
            y = self.loads(s)
            self.assertEqual(B(x), B(y))
            self.assertEqual(x.__dict__, y.__dict__)

    # Register a type with copy_reg, with extension code extcode.  Pickle
    # an object of that type.  Check that the resulting pickle uses opcode
    # (EXT[124]) under proto 2, and not in proto 1.

    def produce_global_ext(self, extcode):
        e = ExtensionSaver(extcode)
        try:
            copy_reg.add_extension(__name__, "MyList", extcode)
            x = MyList([1, 2, 3])
            x.foo = 42
            x.bar = "hello"

            s2 = self.dumps(x, 2)
            self.assertNotIn(__name__, s2)
            self.assertNotIn("MyList", s2)

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
        x = range(n)
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

        n = 2500 
        x = range(n)
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

    def test_dict_chunking(self):
        n = 10  # too small to chunk
        x = dict.fromkeys(range(n))
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

        n = 2500  # expect at least two chunks when proto > 0
        x = dict.fromkeys(range(n))
        s = self.dumps(x)
        y = self.loads(s)
        self.assertEqual(x, y)

    def test_simple_newobj(self):
        x = object.__new__(SimpleNewObj)  # avoid __init__
        x.abc = 666
        s = self.dumps(x)
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
        x = REX_one()
        self.assertEqual(x._reduce_called, 0)
        s = self.dumps(x)
        self.assertEqual(x._reduce_called, 1)
        y = self.loads(s)
        self.assertEqual(y._reduce_called, 0)

    def test_reduce_calls_base(self):
        x = REX_five()
        self.assertEqual(x._reduce_called, 0)
        s = self.dumps(x)
        self.assertEqual(x._reduce_called, 1)
        y = self.loads(s)
        self.assertEqual(y._reduce_called, 1)

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

        try:
            self.dumps(C())
        except (AttributeError, pickle.PickleError, cPickle.PickleError):
            pass
        try:
            self.dumps(D())
        except (AttributeError, pickle.PickleError, cPickle.PickleError):
            pass

    def test_many_puts_and_gets(self):
        # Test that internal data structures correctly deal with lots of
        # puts/gets.
        keys = ("aaa" + str(i) for i in xrange(1))
        large_dict = dict((k, [4, 5, 6]) for k in keys)
        obj = [dict(large_dict), dict(large_dict), dict(large_dict)]
        dumped = self.dumps(obj)
        loaded = self.loads(dumped)
        self.assertEqual(loaded, obj)

    def test_attribute_name_interning(self):
        # Test that attribute names of pickled objects are interned when
        # unpickling.
        x = C()
        x.foo = 42
        x.bar = "hello"
        s = self.dumps(x)
        y = self.loads(s)
        x_keys = sorted(x.__dict__)
        y_keys = sorted(y.__dict__)
        for x_key, y_key in zip(x_keys, y_keys):
            self.assertIs(x_key, y_key)

    def test_pickle_from_3x(self):
        loaded = self.loads(DATA3)
        self.assertEqual(loaded, set([1, 2]))
        
        loaded = self.loads(DATA4)
        self.assertEqual(type(loaded), type(xrange(0)))
        self.assertEqual(list(loaded), list(xrange(5)))

        loaded = self.loads(DATA5)
        self.assertEqual(type(loaded), SimpleCookie)
        self.assertEqual(list(loaded.keys()), ["key"])
        self.assertEqual(loaded["key"].value, "value")


# Test classes for reduce_ex

class REX_one(object):
    _reduce_called = 0
    def __reduce__(self):
        self._reduce_called = 1
        return REX_one, ()
    # No __reduce_ex__ here, but inheriting it from object

class REX_two(object):
    _proto = None
    def __reduce_ex__(self, proto):
        self._proto = proto
        return REX_two, ()
    # No __reduce__ here, but inheriting it from object

class REX_three(object):
    _proto = None
    def __reduce_ex__(self, proto):
        self._proto = proto
        return REX_two, ()
    def __reduce__(self):
        raise TestFailed, "This __reduce__ shouldn't be called"

class REX_four(object):
    _proto = None
    def __reduce_ex__(self, proto):
        self._proto = proto
        return object.__reduce_ex__(self, proto)
    # Calling base class method should succeed

class REX_five(object):
    _reduce_called = 0
    def __reduce__(self):
        self._reduce_called = 1
        return object.__reduce__(self)
    # This one used to fail with infinite recursion

# Test classes for newobj

class MyInt(int):
    sample = 1

class MyLong(long):
    sample = 1L

class MyFloat(float):
    sample = 1.0

class MyComplex(complex):
    sample = 1.0 + 0.0j

class MyStr(str):
    sample = "hello"

class MyUnicode(unicode):
    sample = u"hello \u1234"

class MyTuple(tuple):
    sample = (1, 2, 3)

class MyList(list):
    sample = [1, 2, 3]

class MyDict(dict):
    sample = {"a": 1, "b": 2}

myclasses = [MyInt, MyLong, MyFloat,
             MyComplex,
             MyStr, MyUnicode,
             MyTuple, MyList, MyDict]


class SlotList(MyList):
    __slots__ = ["foo"]

class SimpleNewObj(object):
    def __init__(self, a, b, c):
        # raise an error, to make sure this isn't called
        raise TypeError("SimpleNewObj.__init__() didn't expect to get called")

class AbstractPickleModuleTests(object):

    def test_dump_closed_file(self):
        import os
        f = open(TESTFN, "w")
        try:
            f.close()
            self.assertRaises(ValueError, self.module.dump, 123, f)
        finally:
            os.remove(TESTFN)

    def test_load_closed_file(self):
        import os
        f = open(TESTFN, "w")
        try:
            f.close()
            self.assertRaises(ValueError, self.module.dump, 123, f)
        finally:
            os.remove(TESTFN)

    def test_load_from_and_dump_to_file(self):
        stream = io.BytesIO()
        data = [123, {}, 124]
        self.module.dump(data, stream)
        stream.seek(0)
        unpickled = self.module.load(stream)
        self.assertEqual(unpickled, data)

    def test_incomplete_input(self):
        s = io.BytesIO(b"\xd4")
        self.assertRaises(EOFError, self.module.load, s)

    def test_bad_input(self):
        s = '\xd4'
        self.assertRaises(EOFError, self.module.loads, s)


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


class PickleTests(
        AbstractDataPickleTests,
        AbstractPickleTests, AbstractPickleModuleTests, 
        AbstractAttackPickleTests,
        unittest.TestCase):
    
    def setUp(self):
        super(PickleTests, self).setUp()
        self._pickler = pickle.Pickler()
        self._unpickler = pickle.Unpickler()
        self._dumps = self._pickler.dumps
        self._loads = self._unpickler.loads

    def check_refcount(self):
        self.assertEqual(
            self._pickler.last_refcount, self._unpickler.last_refcount)

    def dumps(self, arg, proto=0, fast=0):
        return self._dumps(arg)

    def loads(self, buf):
        return self._loads(buf)

    module = pickle
    error = KeyError


class FilePicklerTests(unittest.TestCase, AbstractPickleTests):
    error = KeyError

    def check_refcount(self):
        pass

    def dumps(self, arg, proto=0, fast=0):
        f = io.BytesIO()
        p = pickle.Pickler(f)
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


if __name__ == "__main__":
    unittest.main()
