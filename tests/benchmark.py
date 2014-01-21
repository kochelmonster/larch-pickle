#!/usr/bin/python
from __future__ import print_function
#
# Simple serialization banchmark
#

from timeit import timeit 
from tabulate import tabulate
try:
    import cPickle as pickle
except ImportError:
    import pickle

import msgpack
import json
#import cjson
import ujson
import marshal
import larch.pickle as spickle


LOOPS = 200

pdumps = lambda x: pickle.dumps(x, -1)
mdumps = lambda x: marshal.dumps(x, -1)


pdump = lambda x, f: pickle.dump(x, f, -1)
mdump = lambda x, f: marshal.dump(x, f, -1)


serializers = (
    ('cPickle', pdumps, pickle.loads),
    #('json', json.dumps, json.loads),
    #('cjson', cjson.encode, cjson.decode),
    #('ujson', ujson.dumps, ujson.loads),
    #('msgpack', msgpack.dumps, msgpack.loads),
    #('marshal', mdumps, marshal.loads),
    ('spickle', spickle.Pickler(with_refs=True).dumps, spickle.Unpickler().loads),
)


d = {
    'words': """
        Lorem ipsum dolor sit amet, consectetur adipiscing 
        elit. Mauris adipiscing adipiscing placerat. 
        Vestibulum augue augue, 
        pellentesque quis sollicitudin id, adipiscing.
        """,
    'list': range(1000),
    'dict': dict((str(i),'a') for i in range(1000)),
    'int': 100,
    'float': 100.123456
}

def load_documents():
    with open("test.data", "rb") as f:
        try:
            return pickle.load(f, encoding="utf8")
        except TypeError:
            return pickle.load(f)


def measure(documents, loops=LOOPS):
    dump_table = []
    load_table = []

    for title, dumps, loads in serializers:
        packed = [""]
        def do_dump():
            packed[0] = dumps(documents)
            
        def do_load():
            loads(packed[0])

        print(title)
        print("  dump...")
        result = timeit(do_dump, number=loops)
        dump_table.append([title, result, len(packed[0])])
 
        print("  load...")
        result = timeit(do_load, number=loops)
        load_table.append([title, result])

    return dump_table, load_table, loops


def show(dump, load, count):
    dump.sort(key=lambda x: x[1])
    dump.insert(0, ['Package', 'Seconds', "Size"])
 
    load.sort(key=lambda x: x[1])
    load.insert(0, ['Package', 'Seconds'])

    print("\nDump Test (%d loops)" % count)
    print(tabulate(dump, headers="firstrow"))
 
    print("\nLoad Test (%d loops)" % count)
    print(tabulate(load, headers="firstrow"))
        

class Item(object):
    def __init__(self, nr, data, time):
        self.nr = nr
        self.data = data 
        self.time = time


def main():
    documents = load_documents()#[:1000]
    #global d
    #documents = [d]*100
    """
    print "pickle dumps"
    sp = pdumps(documents)
    print len(sp)
    """
    """
    print("spickle dumps")

    documents = documents
    from pprint import pprint
    #pprint(documents)
    sp = spickle.Pickler(with_refs=True).dumps(documents)
    d = spickle.loads(sp)

    print("--------")
    print("equal?", d == documents)
        
    #pprint(d)
    #print("--------")
    #print(repr(sp))
    return
    """
    #from random import choice
    #population = "abcdefghijklmnopqrstuvwxyz"
    #documents = [ "".join(choice(population) for j in range(i)) for i in range(1, 1000) ]*10


    if True:
        print("Test Many Dictionaries")
        print("======================")
        print("len", len(documents))
        d, l, c = measure(documents, 10)
        show(d, l, c)

    if True:
        print()
        print("Test Objects")
        print("============")
        objects = [Item(*args) for args in documents]
        d, l, c = measure(objects, 10)
        show(d, l, c)

    
    string_data = repr(documents).split("{")*2
    if True:
        print()
        print("Test Strings")
        print("============")
        #print("len", len(string_data))
        d, l, c = measure(string_data, 10)
        show(d, l, c)
    
    if True:
        list_data = [[[d]] for d in string_data]
        print()
        print("Test Lists")
        print("==========")
        #print("len", len(list_data))
        d, l, c = measure(list_data, 1)
        show(d, l, c)

    
        


if __name__ == "__main__":
    main()
    print("end main")
