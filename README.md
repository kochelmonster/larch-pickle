## larch.pickle - A secure python pickle replacement

This module can be used as transparent replacement for pickle. It does not suffer the 
vulnerability of original pickle see: http://michael-rushanan.blogspot.de/2012/10/why-python-pickle-is-insecure.html.

Difference to python pickle:
- no memo attribute
- no clear_memo()
- no persistent_id interface
- byte string are always assumed to be utf-8 encoded
- `Pickler` has an additional `with_refs` parameter. Setting `with_refs`
  to `false`, the pickler will ignore object references, this results in
  an extra speed boost.


### Installation
larch-pickle needs the boost library for compilation. If boost
is not in the standard include path install it with:

`python build_ext -I /path/to/boost install`


### Speed compared to some other pickler packages

#### dump Dictionaries (10 loops)
| Package      |   Seconds |     Size |
|:-------------|----------:|---------:|
| marshal      |  0.454694 | 15975952 |
| larch-pickle |  0.586087 |  9714411 |
| ujson        |  1.94068  | 13141354 |
| msgpack      |  1.95001  |  9843459 |
| json         |  2.1489   | 14365311 |
| cPickle      |  4.29243  | 12781866 |
#### load Dictionaries (10 loops)
| Package      |   Seconds |
|:-------------|----------:|
| msgpack      |   1.43802 |
| larch-pickle |   1.53487 |
| marshal      |   1.56561 |
| cPickle      |   2.44472 |
| ujson        |   2.48116 |
| json         |   5.78576 |
#### dump Objects (10 loops)
| Package      |   Seconds |     Size |
|:-------------|----------:|---------:|
| larch-pickle |  0.968418 | 10094415 |
| ujson        |  2.56079  | 13331354 |
| cPickle      |  4.8822   | 12961909 |
#### load Objects (10 loops)
| Package      |   Seconds |
|:-------------|----------:|
| larch-pickle |   1.6902  |
| ujson        |   2.51544 |
| cPickle      |   2.58821 |
#### dump Strings (10 loops)
| Package      |   Seconds |     Size |
|:-------------|----------:|---------:|
| marshal      |  0.582926 | 32826787 |
| msgpack      |  0.980826 | 29464951 |
| json         |  1.18866  | 31966498 |
| ujson        |  1.51086  | 30987525 |
| larch-pickle |  1.70253  | 17054823 |
| cPickle      |  4.21949  | 19871780 |
#### load Strings (10 loops)
| Package      |   Seconds |
|:-------------|----------:|
| larch-pickle |  0.431427 |
| marshal      |  0.449067 |
| msgpack      |  0.549114 |
| cPickle      |  1.70127  |
| ujson        |  1.88499  |
| json         |  3.17667  |
#### dump Lists (10 loops)
| Package      |   Seconds |     Size |
|:-------------|----------:|---------:|
| marshal      |  0.879272 | 42703907 |
| larch-pickle |  3.11243  | 21005671 |
| json         |  3.27417  | 35917346 |
| ujson        |  4.34822  | 34938373 |
| msgpack      |  4.44871  | 31440375 |
| cPickle      | 15.2853   | 33700258 |
#### load Lists (10 loops)
| Package      |   Seconds |
|:-------------|----------:|
| larch-pickle |   2.12795 |
| marshal      |   2.14723 |
| msgpack      |   2.41231 |
| ujson        |   4.27773 |
| json         |   5.29066 |
| cPickle      |   8.1543  |
