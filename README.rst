larch.pickle - A faster and secure python pickle replacement
============================================================

This module can be used as transparent replacement for pickle.

Difference to original python pickle:

    - no memo attribute.
    - no `clear_memo()`.
    - no `persistent_id` interface.
    - byte strings are always assumed to be `utf-8` encoded.
    - `Pickler` has an additional `with_refs` parameter. Setting `with_refs`
      to `false`, the pickler will ignore object references. This can result
      in an extra speed boost.


Installation
------------

larch-pickle needs the boost library for compilation. If boost is not in
the standard include path install it with: ::

  python build_ext -I /path/to/boost install


Security
--------

Version 1.4.0 introduced a secure parameter in Unpickler.
With `secure=True` the Unpickler loads only objects that, are registered
as secure. To register secure objects you can

- use the decorator `secure_unpickle`
- set the attribute `__pickle_secure__ = True`
- add a module name to `secure_modules`


Speed compared to some other pickler packages
---------------------------------------------

dump Dictionaries (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========  ========
Package         Seconds      Size
============  =========  ========
larch-pickle   0.642136   9526217
msgpack        0.77389    9810043
marshal        0.85395   15975952
ujson          1.51786   13101307
Pickle-3.9.0   2.25929   10276493
json           2.75167   14365311
============  =========  ========


load Dictionaries (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========
Package         Seconds
============  =========
larch-pickle    1.6862
Pickle-3.9.0    1.7676
msgpack         1.85972
marshal         1.92646
ujson           2.03244
json            2.1018
============  =========


dump Objects (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========  ========
Package         Seconds      Size
============  =========  ========
larch-pickle   0.735664   9826224
Pickle-3.9.0   2.40565   10416542
============  =========  ========


load Objects (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========
Package         Seconds
============  =========
larch-pickle    1.78888
Pickle-3.9.0    1.8409
============  =========


dump Strings (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========  ========
Package         Seconds      Size
============  =========  ========
msgpack        0.430776  28782143
marshal        0.635346  32481517
larch-pickle   0.881418  10885236
ujson          0.902386  30722275
Pickle-3.9.0   1.0621    17726498
json           1.62853   31701248
============  =========  ========


load Strings (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========
Package         Seconds
============  =========
larch-pickle   0.352779
Pickle-3.9.0   0.633761
msgpack        0.878908
marshal        0.892124
json           1.18237
ujson          1.47554
============  =========


dump Lists (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========  ========
Package         Seconds      Size
============  =========  ========
marshal        0.914561  42358637
larch-pickle   1.75087   14836084
msgpack        2.17429   30757567
ujson          2.44817   34673123
json           4.43027   35652096
Pickle-3.9.0   5.02901   23654090
============  =========  ========


load Lists (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========
Package         Seconds
============  =========
larch-pickle    2.02687
msgpack         2.46098
marshal         2.68831
json            3.11702
ujson           3.53878
Pickle-3.9.0    3.91016
============  =========
