#!/usr/bin/env python
"""
mini 6502 assembler in python
"""
import sys

class SyntaxError(Exception) :
    pass
class AsmError(Exception) :
    pass

class Buf(object) :
    def __init__(self, s) :
        self.buf = s
        self.pos = 0
    def peek(self) :
        if self.pos < len(self.buf) :
            return self.buf[self.pos]
    def next(self) :
        ch = self.peek()
        if ch is not None :
            self.pos += 1
        return ch
    def skipSpaces(self) :
        while self.peek() in [' ', '\t'] :
            self.next()
    def advance(self, n) :
        self.pos += n
        if self.pos > len(self.buf) :
            self.pos = len(self.buf)
    def match(self, s) :
        # XXX case-insensitive matching
        if self.buf[self.pos:].startswith(s) :
            self.advance(len(s))
            return True

class Val(object) :
    def __init__(self, typ, **kw) :
        self.keys = kw.keys()
        self.typ = typ
        for k,v in kw.items() :
            setattr(self, k, v)
    def __repr__(self) :
        return '[Val %s %s]' % (self.typ, ' '.join('%s=%s' % (k, getattr(self, k)) for k in self.keys))
    def __str__(self) :
        return self.__repr__()

def hexVal(ch) :
    return "0123456789ABCDEF".index(ch.upper())

def parseInt(b) :
    n = 0
    if b.match('$') :
        b.skipSpaces()
        start = b.pos
        while b.peek() in "0123456789abcdefABCDEF" :
            n = n * 16 + hexVal(b.next())
    else :
        start = b.pos
        while b.peek() in "0123456789" :
            n = n * 10 + hexVal(b.next())
    if b.pos > start :
        return Val("int", val=n)

def parseVar(b) :
    if b.peek().isalpha() :
        s = ''
        while b.peek().isalpha() or b.peek().isdigit() or b.peek() in "_" :
            s += b.next()
        return Val("var", name=s)

def parseNum(b) :
    """Int or Var"""
    v = parseInt(b)
    if v is None :
        v = parseVar(b)
    return v

def parseImm(b) :
    b.skipSpaces()
    if b.match('#') :
        b.skipSpaces()
        n = parseNum(b)

opcodes = "adc and asl bcc bcs beq bit bmi bne bpl brk bvc bvs clc cld cli clv cmp cpx cpy dec dex dey eor inc inx iny jmp jsr lda ldx ldy lsr nop ora pha php pla plp rol ror rti rts sbc sec sed sei sta stx sty tax tay tsx txa txs tya".split(' ')

def parseOp(b) :
    for op in opcodes :
        if b.match(op) :
            return op

def expect(b, s) :
    if b.match(s) is None :
        raise SyntaxError("expected %r" % s)

def require(x, msg) :
    if x is None :
        raise SyntaxError(msg)

# OpArg types and their syntax
# #         - #num 
# A         - none or "A"
# X,ind     - (addr,X)
# abs       - num       -- can be rel or zpg too
  # rel     - num
  # zpg     - num
# abs,X     - num,X     -- can be zpg,X too
  # zpg,X   - num,X
# abs,Y     - num,Y     -- can be zpg,Y too
  # zpg,Y   - num,Y
# impl      - none
# ind       - (num)
# ind,Y     - (num),Y
def parseOpArg(b) :
    b.skipSpaces()
    num = parseNum(b)
    if num is not None and num.typ == 'var' and num.name.lower() == 'a' :
        v = Val("A")
    elif num is not None :
        b.skipSpaces()
        if b.match(",") :
            var = parseVar(b)
            if var is None or var.name.lower() not in ("x", "y") :
                raise SyntaxError("bad index")
            if var.name.lower() == "x" :
                v = Val("abs,X", val=num)
            else :
                v = Val("abs,Y", val=num)
        else :
            v = Val("abs", val=num)
    elif b.match("#") :
        b.skipSpaces()
        n = parseNum(b)
        if n is None :
            raise SyntaxError("bad immediate")
        v = Val("#", val=n)
    elif b.match("(") :
        b.skipSpaces()
        num = parseNum(b)
        if num is None :
            raise SyntaxError("missing indirect address")
        b.skipSpaces()
        if b.match(",") :
            b.skipSpaces()
            var = parseVar(b)
            if var is not None or var.name.lower != "x" :
                raise SyntaxError("bad index")
            b.skipSpaces()
            expect(b, ")")
            v = Val("X,ind", val=var)
        elif b.match(")") :
            b.skipSpaces()
            if b.match(",") :
                b.skipSpaces()
                var = parseVar(b)
                if var is not None or var.name.lower != "y" :
                    raise SyntaxError("bad index")
                v = Val("ind,Y", val=var)
            else :
                v = Val("ind", val=var)
    else :
        v = Val("impl")
    return v
    
opArgs = {
    'ADC': ('#', 'X,ind', 'abs', 'abs,X', 'abs,Y', 'ind,Y', 'zpg', 'zpg,X'),
    'AND': ('#', 'X,ind', 'abs', 'abs,X', 'abs,Y', 'ind,Y', 'zpg', 'zpg,X'),
    'ASL': ('A', 'abs', 'abs,X', 'zpg', 'zpg,X'),
    'BCC': ('rel',),
    'BCS': ('rel',),
    'BEQ': ('rel',),
    'BIT': ('abs', 'zpg'),
    'BMI': ('rel',),
    'BNE': ('rel',),
    'BPL': ('rel',),
    'BRK': ('impl',),
    'BVC': ('rel',),
    'BVS': ('rel',),
    'CLC': ('impl',),
    'CLD': ('impl',),
    'CLI': ('impl',),
    'CLV': ('impl',),
    'CMP': ('#', 'X,ind', 'abs', 'abs,X', 'abs,Y', 'ind,Y', 'zpg', 'zpg,X'),
    'CPX': ('#', 'abs', 'zpg'),
    'CPY': ('#', 'abs', 'zpg'),
    'DEC': ('abs', 'abs,X', 'zpg', 'zpg,X'),
    'DEX': ('impl',),
    'DEY': ('impl',),
    'EOR': ('#', 'X,ind', 'abs', 'abs,X', 'abs,Y', 'ind,Y', 'zpg', 'zpg,X'),
    'INC': ('abs', 'abs,X', 'zpg', 'zpg,X'),
    'INX': ('impl',),
    'INY': ('impl',),
    'JMP': ('abs', 'ind'),
    'JSR': ('abs',),
    'LDA': ('#', 'X,ind', 'abs', 'abs,X', 'abs,Y', 'ind,Y', 'zpg', 'zpg,X'),
    'LDX': ('#', 'abs', 'abs,Y', 'zpg', 'zpg,Y'),
    'LDY': ('#', 'abs', 'abs,X', 'zpg', 'zpg,X'),
    'LSR': ('A', 'abs', 'abs,X', 'zpg', 'zpg,X'),
    'NOP': ('impl',),
    'ORA': ('#', 'X,ind', 'abs', 'abs,X', 'abs,Y', 'ind,Y', 'zpg', 'zpg,X'),
    'PHA': ('impl',),
    'PHP': ('impl',),
    'PLA': ('impl',),
    'PLP': ('impl',),
    'ROL': ('A', 'abs', 'abs,X', 'zpg', 'zpg,X'),
    'ROR': ('A', 'abs', 'abs,X', 'zpg', 'zpg,X'),
    'RTI': ('impl',),
    'RTS': ('impl',),
    'SBC': ('#', 'X,ind', 'abs', 'abs,X', 'abs,Y', 'ind,Y', 'zpg', 'zpg,X'),
    'SEC': ('impl',),
    'SED': ('impl',),
    'SEI': ('impl',),
    'STA': ('X,ind', 'abs', 'abs,X', 'abs,Y', 'ind,Y', 'zpg', 'zpg,X'),
    'STX': ('abs', 'zpg', 'zpg,Y'),
    'STY': ('abs', 'zpg', 'zpg,X'),
    'TAX': ('impl',),
    'TAY': ('impl',),
    'TSX': ('impl',),
    'TXA': ('impl',),
    'TXS': ('impl',),
    'TYA': ('impl',),
}

equiv = {
    'rel': 'abs',
    'zpg': 'abs',
    'zpg,X': 'abs,X',
    'zpg,Y': 'abs,Y',
}

def equivTyp(t) :
    """Since some arg types have the same syntax, return the canonical arg type for each syntax type."""
    if t in equiv :
        return equiv[t]
    return t

def checkArgType(op, arg) :
    typ = equivTyp(arg.typ)
    for acceptable in opArgs[op.upper()] :
        if arg.typ == equivTyp(acceptable) :
            return acceptable
    raise SyntaxError("bad argument type %r for opcode %r" % (arg.typ, op))

def parseLine(b) :
    b.skipSpaces()
    op = parseOp(b)
    if op is None :
        var = parseVar(b)

    if op is not None :
        b.skipSpaces()
        arg = parseOpArg(b) # optional
        arg.typ = checkArgType(op, arg)
        v = Val("op", op=op, arg=arg)
    elif var is not None :
        b.skipSpaces()
        expect(b, "=")
        b.skipSpaces()
        expect(b, "*")
        v = Val("setvar", var=var.name)
    elif b.match("*") :
        b.skipSpaces()
        expect(b, "=")
        b.skipSpaces()
        num = parseNum(b)
        require(num, "missing value")
        v =  Val("setdot", val=num)
    else :
        raise SyntaxError("unexpected")

    b.skipSpaces()
    if not b.match("\n") :
        raise SyntaxError("expected EOL, got %r" % b.peek())
    return v

def parseFile(fn) :
    f = file(fn)
    lno = 0
    prog = []
    try :
        for l in f :
            lno += 1
            b = Buf(l)
            v = parseLine(b)
            prog.append(v)
        return prog
    except SyntaxError, e :
        print b.buf.replace('\n', '')
        spaces = ' ' * b.pos
        print '%s^  line %d pos %d: %s' % (spaces, lno, b.pos, e)

# (opname,addrmode) => (opcode, size)
opTab = {
    ('brk','impl'): (0,1),
    ('ora','X,ind'): (1,2),
    ('ora','zpg'): (5,2),
    ('asl','zpg'): (6,2),
    ('php','impl'): (8,1),
    ('ora','#'): (9,2),
    ('asl','A'): (10,1),
    ('ora','abs'): (13,3),
    ('asl','abs'): (14,3),
    ('bpl','rel'): (16,2),
    ('ora','ind,Y'): (17,2),
    ('ora','zpg,X'): (21,2),
    ('asl','zpg,X'): (22,2),
    ('clc','impl'): (24,1),
    ('ora','abs,Y'): (25,3),
    ('ora','abs,X'): (29,3),
    ('asl','abs,X'): (30,3),
    ('jsr','abs'): (32,3),
    ('and','X,ind'): (33,2),
    ('bit','zpg'): (36,2),
    ('and','zpg'): (37,2),
    ('rol','zpg'): (38,2),
    ('plp','impl'): (40,1),
    ('and','#'): (41,2),
    ('rol','A'): (42,1),
    ('bit','abs'): (44,3),
    ('and','abs'): (45,3),
    ('rol','abs'): (46,3),
    ('bmi','rel'): (48,2),
    ('and','ind,Y'): (49,2),
    ('and','zpg,X'): (53,2),
    ('rol','zpg,X'): (54,2),
    ('sec','impl'): (56,1),
    ('and','abs,Y'): (57,3),
    ('and','abs,X'): (61,3),
    ('rol','abs,X'): (62,3),
    ('rti','impl'): (64,1),
    ('eor','X,ind'): (65,2),
    ('eor','zpg'): (69,2),
    ('lsr','zpg'): (70,2),
    ('pha','impl'): (72,1),
    ('eor','#'): (73,2),
    ('lsr','A'): (74,1),
    ('jmp','abs'): (76,3),
    ('eor','abs'): (77,3),
    ('lsr','abs'): (78,3),
    ('bvc','rel'): (80,2),
    ('eor','ind,Y'): (81,2),
    ('eor','zpg,X'): (85,2),
    ('lsr','zpg,X'): (86,2),
    ('cli','impl'): (88,1),
    ('eor','abs,Y'): (89,3),
    ('eor','abs,X'): (93,3),
    ('lsr','abs,X'): (94,3),
    ('rts','impl'): (96,1),
    ('adc','X,ind'): (97,2),
    ('adc','zpg'): (101,2),
    ('ror','zpg'): (102,2),
    ('pla','impl'): (104,1),
    ('adc','#'): (105,2),
    ('ror','A'): (106,1),
    ('jmp','ind'): (108,2),
    ('adc','abs'): (109,3),
    ('ror','abs'): (110,3),
    ('bvs','rel'): (112,2),
    ('adc','ind,Y'): (113,2),
    ('adc','zpg,X'): (117,2),
    ('ror','zpg,X'): (118,2),
    ('sei','impl'): (120,1),
    ('adc','abs,Y'): (121,3),
    ('adc','abs,X'): (125,3),
    ('ror','abs,X'): (126,3),
    ('sta','X,ind'): (129,2),
    ('sty','zpg'): (132,2),
    ('sta','zpg'): (133,2),
    ('stx','zpg'): (134,2),
    ('dey','impl'): (136,1),
    ('txa','impl'): (138,1),
    ('sty','abs'): (140,3),
    ('sta','abs'): (141,3),
    ('stx','abs'): (142,3),
    ('bcc','rel'): (144,2),
    ('sta','ind,Y'): (145,2),
    ('sty','zpg,X'): (148,2),
    ('sta','zpg,X'): (149,2),
    ('stx','zpg,Y'): (150,2),
    ('tya','impl'): (152,1),
    ('sta','abs,Y'): (153,3),
    ('txs','impl'): (154,1),
    ('sta','abs,X'): (157,3),
    ('ldy','#'): (160,2),
    ('lda','X,ind'): (161,2),
    ('ldx','#'): (162,2),
    ('ldy','zpg'): (164,2),
    ('lda','zpg'): (165,2),
    ('ldx','zpg'): (166,2),
    ('tay','impl'): (168,1),
    ('lda','#'): (169,2),
    ('tax','impl'): (170,1),
    ('ldy','abs'): (172,3),
    ('lda','abs'): (173,3),
    ('ldx','abs'): (174,3),
    ('bcs','rel'): (176,2),
    ('lda','ind,Y'): (177,2),
    ('ldy','zpg,X'): (180,2),
    ('lda','zpg,X'): (181,2),
    ('ldx','zpg,Y'): (182,2),
    ('clv','impl'): (184,1),
    ('lda','abs,Y'): (185,3),
    ('tsx','impl'): (186,1),
    ('ldy','abs,X'): (188,3),
    ('lda','abs,X'): (189,3),
    ('ldx','abs,Y'): (190,3),
    ('cpy','#'): (192,2),
    ('cmp','X,ind'): (193,2),
    ('cpy','zpg'): (196,2),
    ('cmp','zpg'): (197,2),
    ('dec','zpg'): (198,2),
    ('iny','impl'): (200,1),
    ('cmp','#'): (201,2),
    ('dex','impl'): (202,1),
    ('cpy','abs'): (204,3),
    ('cmp','abs'): (205,3),
    ('dec','abs'): (206,3),
    ('bne','rel'): (208,2),
    ('cmp','ind,Y'): (209,2),
    ('cmp','zpg,X'): (213,2),
    ('dec','zpg,X'): (214,2),
    ('cld','impl'): (216,1),
    ('cmp','abs,Y'): (217,3),
    ('cmp','abs,X'): (221,3),
    ('dec','abs,X'): (222,3),
    ('cpx','#'): (224,2),
    ('sbc','X,ind'): (225,2),
    ('cpx','zpg'): (228,2),
    ('sbc','zpg'): (229,2),
    ('inc','zpg'): (230,2),
    ('inx','impl'): (232,1),
    ('sbc','#'): (233,2),
    ('nop','impl'): (234,1),
    ('cpx','abs'): (236,3),
    ('sbc','abs'): (237,3),
    ('inc','abs'): (238,3),
    ('beq','rel'): (240,2),
    ('sbc','ind,Y'): (241,2),
    ('sbc','zpg,X'): (245,2),
    ('inc','zpg,X'): (246,2),
    ('sed','impl'): (248,1),
    ('sbc','abs,Y'): (249,3),
    ('sbc','abs,X'): (253,3),
    ('inc','abs,X'): (254,3),
}

def getVar(vars, nm, req) :
    if not req :
        return 0
    if nm not in vars :
        raise AsmError("unknown variable %r" % nm)
    return vars[nm]
    
def evalNum(vars, num, reqVar) :
    if num.typ == 'int' :
        return num.val
    elif num.typ == 'var' :
        return getVar(vars, num.name, reqVar)
    else :
        assert 0

def encSigned8(n) :
    if n < -128 or n > 127 :
        raise AsmError("offset too large: %r" % n)
    if n < 0 :
        return 256 + n
    return n

def evalOpArg(vars, a, reqVar) :
    if a.typ in ['A', 'impl'] :
        return []
    elif a.typ in  ['#', 'zpg', 'zpg,X', 'zpg,Y'] :
        n = evalNum(vars, a.val, reqVar)
        if n > 255 :
            raise AsmError("byte value too big: %x" % n)
        return [n]
    elif a.typ in ['#', 'abs', 'abs,X', 'ind', 'X,ind', 'ind,Y'] :
        #print a
        n = evalNum(vars, a.val, reqVar)
        if n > 65535 :
            raise AsmError("addr value too big: %x" % n)
        return [n & 0xff, n >> 8]
    elif a.typ == 'rel' :
        n = 0
        if reqVar :
            v = evalNum(vars, a.val, reqVar)
            dot = vars['*']
            n = encSigned8(v - (dot+2))  # rel insns are 2 bytes long
        return [n]
    else :
        assert 0

def execLine(vars, l, reqVar) :
    if l.typ == 'setdot' :
        #print l
        vars['*'] = evalNum(vars, l.val, reqVar)
        bs = []
    elif l.typ == 'setvar' :
        #print l
        vars[l.var] = vars['*']
        bs = []
    elif l.typ == 'op' :
        k = l.op, l.arg.typ
        opnum,sz = opTab[k]
        bs = evalOpArg(vars, l.arg, reqVar)
        bs = [opnum] + bs
        #print opnum, bs, sz, k
        assert sz == len(bs)
    else :
        assert 0
    vars['*'] += len(bs)
    return bs

def asmPass(vars, prog, reqVar) :
    vars['*'] = 0

    # XXX upgrades from abs to zpg
    base = None
    x = []
    try :
        lno = 0
        for l in prog :
            lno += 1
            dot = vars['*']
            bs = execLine(vars, l, reqVar)
            if bs :
                if base is None :
                    base = dot
                # pad out to current dot
                while (base + len(x)) & 0xffff < dot :
                    x += [0]
                x += bs
        return base, x
    except AsmError, e :
        print 'line %d: %s' % (lno, e)

def asmProg(prog) :
    vars = {'*': '0'}
    #print 'pass 1'
    if asmPass(vars, prog, 0) is None :
        return
    #print 'pass 2'
    return asmPass(vars, prog, 1)
    
# XXX capture first address
def asm(fn) :
    prog = parseFile(fn)
    if prog is not None :
        return asmProg(prog)

for fn in sys.argv[1:] :
    print fn
    r = asm(fn)
    if r :
        base,bs = r
        print '%04x: %s' % (base, ' '.join('%02x' % b for b in bs))
