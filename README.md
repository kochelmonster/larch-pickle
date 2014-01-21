larch-pickle
============

larch.pickle - A secure python pickle replacement


This module can be used as transparent replacement for pickle.
It does not suffer the vulnerability of original pickle and is 
reasonable fast.

Difference to python pickle:
 - no memo attribute
 - no clear_memo()
 - no persistent_id interface
 - byte string are always assumed to be utf-8 encoded


