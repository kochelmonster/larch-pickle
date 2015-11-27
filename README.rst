larch.pickle - A secure python pickle replacement
=================================================

This module can be used as transparent replacement for pickle. It does
not suffer the vulnerability of original pickle described in the following
article:
http://michael-rushanan.blogspot.de/2012/10/why-python-pickle-is-insecure.html.

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



Speed compared to some other pickler packages
---------------------------------------------

dump Dictionaries (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========  ========
Package         Seconds      Size
============  =========  ========
marshal        0.46141   15975952
larch-pickle   0.664333   9714411
ujson          1.94214   13141354
msgpack        2.04704    9843459
json           2.14117   14365311
cPickle        4.09599   12781866
============  =========  ========


load Dictionaries (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========
Package         Seconds
============  =========
msgpack         1.38378
marshal         1.49512
larch-pickle    1.51489
ujson           2.42431
cPickle         2.42524
json            6.04131
============  =========


dump Objects (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========  ========
Package         Seconds      Size
============  =========  ========
larch-pickle    1.07443  10094415
ujson           2.55502  13331354
cPickle         4.70805  12961909
============  =========  ========


load Objects (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========
Package         Seconds
============  =========
larch-pickle    1.6615
ujson           2.45786
cPickle         2.58697
============  =========


dump Strings (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========  ========
Package         Seconds      Size
============  =========  ========
marshal        0.56747   32826787
msgpack        0.975226  29464951
larch-pickle   1.16368   12103729
json           1.19005   31966498
ujson          1.51648   30987525
cPickle        4.12952   19871780
============  =========  ========


load Strings (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========
Package         Seconds
============  =========
larch-pickle   0.353255
marshal        0.435936
msgpack        0.469068
cPickle        1.72308
ujson          1.82656
json           3.01798
============  =========


dump Lists (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========  ========
Package         Seconds      Size
============  =========  ========
marshal        0.861886  42703907
larch-pickle   2.33574   16054577
json           3.11054   35917346
ujson          4.4284    34938373
msgpack        5.55321   31440375
cPickle       15.5531    33700258
============  =========  ========


load Lists (10 loops)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

============  =========
Package         Seconds
============  =========
larch-pickle    2.07305
marshal         2.14713
msgpack         2.46054
ujson           4.14067
json            5.20221
cPickle         8.1974
============  =========

