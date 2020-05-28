#!/usr/bin/env python

import os, sys
from asm import asm
from d64 import Disk

disk = 'test.d64'
fn = sys.argv[1]
r = asm(fn)
if r :
    base,bs = r
    bs = ''.join(chr(b) for b in bs)
    d = Disk('asm.d64')
    d.removeFile("ASM")
    d.writeFile("ASM", base, bs)
    d.sync()

