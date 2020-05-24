#!/usr/bin/env python
"""
See http://unusedino.de/ec64/technical/formats/d64.html
"""
import struct

class Error(Exception) :
    pass

Sanity = True
#Sanity = False

def pad(s, n, ch) :
    while len(s) < n :
        s += ch
    return s

def decBAM(tno, bs) :
    fr,b0,b1,b2 = bs
    bs = (b2<<16) | (b1<<8) | b0
    bits = set(b for b in xrange(24) if (bs & (1<<b)) != 0)
    if fr != len(bits) :
        print "warning: wrong free bits for track %d - %d actual vs %d" % (tno, len(bits), fr)
    return bits

def encBAM(fr) :
    bits = 0
    for b in fr :
        bits |= (1 << b)
    return len(fr), (bits>>0)&0xff, (bits >> 8)&0xff, (bits >> 16) & 0xff

class BAM(object) :
    """
  Bytes:$00-01: Track/Sector location of the first directory sector (should
                be set to 18/1 but it doesn't matter, and don't trust  what
                is there, always go to 18/1 for first directory entry)
            02: Disk DOS version type (see note below)
                  $41 ("A")
            03: Unused
         04-8F: BAM entries for each track, in groups  of  four  bytes  per
                track, starting on track 1 (see below for more details)
         90-9F: Disk Name (padded with $A0)
         A0-A1: Filled with $A0
         A2-A3: Disk ID
            A4: Usually $A0
         A5-A6: DOS type, usually "2A"
         A7-AA: Filled with $A0
         AB-FF: Normally unused ($00), except for 40 track extended format,
                see the following two entries:
         AC-BF: DOLPHIN DOS track 36-40 BAM entries (only for 40 track)
         C0-D3: SPEED DOS track 36-40 BAM entries (only for 40 track)
    """
    def __init__(self) :
        pass

    def fromBytes(self, bs) :
        assert len(bs) == 256
        t,s,v,z = struct.unpack("<BBBB", bs[0:4])
        rawBams = [struct.unpack("<BBBB", bs[4 + 4*n : 4 + 4 + 4*n]) for n in xrange(35)]
        nm = bs[0x90:0xa0].rstrip('\xa0')
        did,a0,dtyp = struct.unpack("<HBH", bs[0xa2 : 0xa7])
        self.dir = (t,s)
        self.ver = v
        self.name = nm
        self.id = did
        self.a0 = a0       # worth tracking?
        self.dtype = dtyp
        self.bam = [decBAM(n,rb) for n,rb in enumerate(rawBams)]
        return self

    def toBytes(self) :
        d1 = struct.pack('<BBBB', self.dir[0], self.dir[1], self.ver, 0)
        rawBams = ''.join(struct.pack('<BBBB', *encBAM(b)) for b in self.bam)
        d2 = struct.pack('<HBH', self.id, self.a0, self.dtype)
        zeros = '\0' * 85
        d = d1 + rawBams + pad(self.name, 16, '\xa0') + '\xa0\xa0' + d2 + '\xa0\xa0\xa0\xa0' + zeros
        assert len(d) == 256
        return d

    def __str__(self) :
        def tfree(n, f) :
            return '[%d: %s]' % (n, ' '.join(('%d' % sect) for sect in sorted(f)))
        free = '[free %s]' % ' '.join(tfree(n, f) for (n,f) in enumerate(self.bam))
        return '[BAM %r dir@%s ver %x, ID %x, disk %x free: %s]' % (self.name, self.dir, self.ver, self.id, self.dtype, free)

class Dirent(object) :
    """
    Bytes: $00-1F: First directory entry
          00-01: Track/Sector location of next directory sector ($00 $00 if
                 not the first entry in the sector)
             02: File type.
                 Typical values for this location are:
                   $00 - Scratched (deleted file entry)
                    80 - DEL
                    81 - SEQ
                    82 - PRG
                    83 - USR
                    84 - REL
                 Bit 0-3: The actual filetype
                          000 (0) - DEL
                          001 (1) - SEQ
                          010 (2) - PRG
                          011 (3) - USR
                          100 (4) - REL
                          Values 5-15 are illegal, but if used will produce
                          very strange results. The 1541 is inconsistent in
                          how it treats these bits. Some routines use all 4
                          bits, others ignore bit 3,  resulting  in  values
                          from 0-7.
                 Bit   4: Not used
                 Bit   5: Used only during SAVE-@ replacement
                 Bit   6: Locked flag (Set produces ">" locked files)
                 Bit   7: Closed flag  (Not  set  produces  "*", or "splat"
                          files)
          03-04: Track/sector location of first sector of file
          05-14: 16 character filename (in PETASCII, padded with $A0)
          15-16: Track/Sector location of first side-sector block (REL file
                 only)
             17: REL file record length (REL file only, max. value 254)
          18-1D: Unused (except with GEOS disks)
          1E-1F: File size in sectors, low/high byte  order  ($1E+$1F*256).
                 The approx. filesize in bytes is <= #sectors * 254
    """
    def __init__(self) :
        pass

    def fromBytes(self, bs) :
        assert len(bs) == 32
        lt,ls,ft,dt,ds,fn,sst,sss,rl,skip,sz = struct.unpack("<BBBBB16sBBB6sH", bs)
        self.link = lt,ls
        self.typ = ft
        self.loc = dt,ds
        self.name = fn.rstrip('\xa0')
        self.side = sst,sss
        self.rlen = rl
        self.size = sz
        return self

    def toBytes(self) :
        skip = '\0' * 6
        d = struct.pack("<BBBBB16sBBB6sH", self.link[0], self.link[1], self.typ, self.loc[0], self.loc[1], pad(self.name, 16, '\xa0'), self.side[0], self.side[1], self.rlen, skip, self.size)
        assert len(d) == 32
        return d

    def __str__(self) :
        return '[%r @ %s, type %x, size %d, link %s]' % (self.name, self.loc, self.typ, self.size, self.link)


# TrackNum => (Sectors, SectorOffset)
geom = {
    1: (21, 0),
    2: (21, 21),
    3: (21, 42),
    4: (21, 63),
    5: (21, 84),
    6: (21, 105),
    7: (21, 126),
    8: (21, 147),
    9: (21, 168),
    10: (21, 189),
    11: (21, 210),
    12: (21, 231),
    13: (21, 252),
    14: (21, 273),
    15: (21, 294),
    16: (21, 315),
    17: (21, 336),
    18: (19, 357),
    19: (19, 376),
    20: (19, 395),
    21: (19, 414),
    22: (19, 433),
    23: (19, 452),
    24: (19, 471),
    25: (18, 490),
    26: (18, 508),
    27: (18, 526),
    28: (18, 544),
    29: (18, 562),
    30: (18, 580),
    31: (17, 598),
    32: (17, 615),
    33: (17, 632),
    34: (17, 649),
    35: (17, 666),
}

def getSecOffset(t, s) :
    if t not in geom :
        raise Error("bad track number %d" % t)
    ns,off = geom[t]
    if s < 0 or s >= ns :
        raise Error("bad sector number %d for track %d" % (t,s))
    return off + s

def readSector(fn, t, s) :
    f = file(fn, 'r+b')
    f.seek(getSecOffset(t,s) * 256)
    d = f.read(256)
    f.close()
    return d

def writeSector(fn, t, s, d) :
    assert len(d) == 256
    f = file(fn, 'r+b')
    f.seek(getSecOffset(t,s) * 256)
    d = f.write(d)
    f.close()

class Disk(object) :
    def __init__(self, fn) :
        self.fn = fn
        self.readBAM()
        self.readDir()
    def readBAM(self) :
        d = readSector(self.fn, 18, 0)
        self.bam = BAM().fromBytes(d)
        if Sanity :
            d2 = self.bam.toBytes()
            assert d == d2
    def writeBAM(self) :
        d = self.bam.toBytes()
        writeSector(self.fn, 18, 0, d)
    def sync(self) :
        self.writeDir()
        self.writeBAM()

    def readDir(self) :
        t,s = 18,1
        while t != 0 :
            d = readSector(self.fn, t, s)
            self.dir = [Dirent().fromBytes(d[n*32 : 32 + n*32]) for n in xrange(8)]
            t,s = self.dir[0].link
            assert t == 0 # just one block for now
            if Sanity :
                d2 = ''.join(e.toBytes() for e in self.dir)
                assert d == d2
    def writeDir(self) :
        assert len(self.dir) == 8
        d = ''.join(e.toBytes() for e in self.dir)
        writeSector(self.fn, 18, 1, d)
 
    def fileSectors(self, loc) :
        t,s = loc
        while t != 0 :
            d = readSector(self.fn, t, s)
            t2,s2 = struct.unpack('<BB', d[0:2])
            if t2 == 0 :
                sz = s2
            else :
                sz = 256
            print 'read', t2,s2,sz, d.encode('hex')
            yield t,s,d[2:sz]
            t,s = t2,s2

    def freeSector(self, t, s) :
        assert t > 0
        self.bam.bam[t-1].add(s)

    def allocSector(self) :
        for t,fr in enumerate(self.bam.bam) :
            if fr :
                return t+1, fr.pop()

    def freeFile(self, loc) :
        for t,s,d in self.fileSectors(loc) :
            self.freeSector(t,s)
            
    def removeFile(self, fn) :
        for d in self.dir :
            if d.name == fn :
                self.freeFile(self.dir.loc)
                d.typ == 0
                d.name = '\0' * 16
                return True

    def readFile(self, fn) :
        for d in self.dir :
            if d.name == fn :
                dat = ''.join(dat for t,s,dat in self.fileSectors(d.loc))
                assert len(dat) >= 2
                addr = struct.unpack("<H", dat[0:2])
                return addr, dat[2:]

    def writeData(self, bs) :
        ours,rest = bs[:254], bs[254:]
        if rest :
            (lt,ls),sz = self.writeData(rest)
        else :
            (lt,ls),sz = (0, len(bs)+2), 0
        t,s = self.allocSector()
        dat = struct.pack('<BB', lt,ls) + pad(ours, 254, '\0')
        print 'write', t,s, dat.encode('hex')
        writeSector(self.fn, t, s, dat)
        return (t,s),sz+1

    def writeFile(self, fn, addr, dat) :
        assert addr < 65536
        found = None
        empty = None
        for d in self.dir :
            if d.name == fn :
                found = d
            if d.typ == 0 :
                empty = d
        if found is not None :
            self.freeFile(found.loc)
        else :
            found = empty
        if found is not None :
            d.name = fn
            d.typ = 0x82
            bs = struct.pack('<H', addr) + dat
            loc = self.allocSector()
            d.loc,d.size = self.writeData(bs)
            return True

"""
def cmp(xs, ys) :
    for n in xrange(256) :
        if xs[n] != ys[n] :
            print '%02x: %02x vs %02x' % (n, ord(xs[n]), ord(ys[n]))
"""

def test() :
    d = Disk('testDisk.d64')
    #print d.bam
    print 'disk', d.bam.name,
    print '%d sectors free' % sum(len(fr) for fr in d.bam.bam)
    for e in d.dir :
        print ' ', e
    if 0 :
        d.dir[0].name = 'RENAME'
        d.bam.name = 'MYDISK'
        d.sync()
    if 1 :
        d.writeFile("ABC", 0xc000, "AABBCCDDEEFFGG")
        d.sync()
    #print repr(d.readFile('DIR'))
    print repr(d.readFile('RENAME'))

