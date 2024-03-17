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

=============  =========  ========
Package          Seconds      Size
=============  =========  ========
larch-pickle    0.291857   9356357
marshal         0.344505  15975952
msgpack         0.368878   9810043
ujson           0.550575  13101307
json            0.815204  14365311
Pickle-3.12.2   1.16181   10276493
=============  =========  ========


load Dictionaries (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

=============  =========
Package          Seconds
=============  =========
larch-pickle    0.719275
marshal         0.767289
msgpack         0.817542
Pickle-3.12.2   0.847736
json            0.91282
ujson           0.930489
=============  =========


dump Objects (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

=============  =========  ========
Package          Seconds      Size
=============  =========  ========
larch-pickle    0.337152   9656364
Pickle-3.12.2   1.15342   10416542
=============  =========  ========


load Objects (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

=============  =========
Package          Seconds
=============  =========
larch-pickle    0.794334
Pickle-3.12.2   0.820135
=============  =========


dump Strings (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

=============  =========  ========
Package          Seconds      Size
=============  =========  ========
marshal         0.215026  32481517
msgpack         0.251937  28782143
larch-pickle    0.418834  10885236
json            0.513742  31701248
ujson           0.537478  30722275
Pickle-3.12.2   0.633869  17726498
=============  =========  ========


load Strings (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

=============  =========
Package          Seconds
=============  =========
larch-pickle    0.206729
Pickle-3.12.2   0.253017
marshal         0.359512
msgpack         0.360152
json            0.527622
ujson           0.673696
=============  =========