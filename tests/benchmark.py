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

VERBOSE = False
LOOPS = 10

pdumps = lambda x: pickle.dumps(x, -1)
mdumps = lambda x: marshal.dumps(x, -1)


pdump = lambda x, f: pickle.dump(x, f, -1)
mdump = lambda x, f: marshal.dump(x, f, -1)


serializers = (
    ('cPickle', pdumps, pickle.loads),
    ('json', json.dumps, json.loads),
    #('cjson', cjson.encode, cjson.decode),
    ('ujson', ujson.dumps, ujson.loads),
    ('msgpack', msgpack.dumps, msgpack.loads),
    ('marshal', mdumps, marshal.loads),
    ('larch-pickle', spickle.Pickler(with_refs=True).dumps, spickle.Unpickler().loads),
)


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

        if VERBOSE:
            print(title)
            print("  dump...")
            
        try:
            result = timeit(do_dump, number=loops)
        except:
            continue
        dump_table.append([title, result, len(packed[0])])
 
        if VERBOSE:
            print("  load...")
        result = timeit(do_load, number=loops)
        load_table.append([title, result])

    return dump_table, load_table, loops


def show(title, dump, load, count):
    dump.sort(key=lambda x: x[1])
    dump.insert(0, ['Package', 'Seconds', "Size"])
 
    load.sort(key=lambda x: x[1])
    load.insert(0, ['Package', 'Seconds'])

    print("### dump {} ({} loops)".format(title, count))
    print(tabulate(dump, headers="firstrow", tablefmt="pipe"))
 
    print("### load {} ({} loops)".format(title, count))
    print(tabulate(load, headers="firstrow", tablefmt="pipe"))
        


class Item(object):
    def __init__(self, nr, data, time):
        self.nr = nr
        self.data = data 
        self.time = time


def main():
    documents = load_documents()

    if True:
        #print("len", len(documents))
        d, l, c = measure(documents, LOOPS)
        show("Dictionaries", d, l, c)

    if True:
        objects = [Item(*args) for args in documents]
        d, l, c = measure(objects, LOOPS)
        show("Objects", d, l, c)

    
    string_data = repr(documents).split("{")*2
    if True:
        #print("len", len(string_data))
        d, l, c = measure(string_data, LOOPS)
        show("Strings", d, l, c)
    
    if True:
        list_data = [[[d]] for d in string_data]
        #print("len", len(list_data))
        d, l, c = measure(list_data, LOOPS)
        show("Lists", d, l, c)


if __name__ == "__main__":
    main()

