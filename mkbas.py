#!/usr/bin/env python

import os, sys
from asm import asm

fn = sys.argv[1]
r = asm(fn)
if r :
    base,bs = r
    cnt = len(bs)-1
    lno = 10
    while bs :
        xs,bs = bs[:8], bs[8:]
        dat = ', '.join(str(x) for x in xs)
        print '%d data' % lno, dat
        lno += 10
    print '%d for i = 0 to %d: read a: poke 49152+i,a: next' % (lno, cnt)

