#!/usr/bin/env python
"""
Simple BASIC interpretter in simple python.
Goal: keep it simple. functions, but no classes.
- I used exception handling for non-local goto for error handling
  but tried to keep their use limited
"""

import sys

# --------------
# Parser
# --------------

class SyntaxError(Exception) :
    pass

# this is hokey, I thought it would simplify things a little, but
# it was probably not worth it... consider removing this
def get(o, *names) :
    """Return a list of values from object"""
    vs = []
    for name in names :
        vs.append(o[name])
    return vs

def makeBuf(x) :
    """Make a new parse buffer"""
    return {'buf': x, 'pos': 0, 'start': 0}

def peek(b) :
    """Peek at the next character in the buffer without consuming it"""
    buf,pos = get(b, 'buf', 'pos')
    if pos >= len(buf) :
        return None
    return buf[pos]

def skip(b, n) :
    """Skip some characters in the buffer"""
    b['pos'] += n

def next(b) :
    """Consume and return the next character in the buffer"""
    ch = peek(b)
    if ch is not None :
        skip(b, 1)
    return ch

def require(x) :
    """Syntax error if x was not parsed"""
    if x is None :
        raise SyntaxError()

def expect(b, ch) :
    """Consume a character and syntax error if its not what we want"""
    if peek(b) != ch :
        raise SyntaxError()
    return next(b)

def getParsed(b, start) :
    """Get everything parsed from the start position to the current position"""
    buf,pos = get(b, 'buf', 'pos')
    return buf[start : pos]

def skipSpaces(b) :
    """Consume consecutive spaces in the buffer"""
    while peek(b) == ' ' :
        next(b)

def parseInt(b) :
    """Optionally parse an integer from the buffer, returning its value"""
    skipSpaces(b)
    start = b['pos']
    val = 0
    while peek(b) and peek(b).isdigit() :
        ch = next(b)
        val = val * 10 + (ord(ch) - 48)
    if start != b['pos'] :
        return val
kws = [ 
    "new", "list", "run", 
    "if", "then", # "else"
    "for", "to", "step", "next",
    "goto",
    "print",
    "set",
]

def parseKeyword(b) :
    """Optionally parse a keyword from the buffer, returning the keyword."""
    buf,pos = get(b, 'buf', 'pos')
    skipSpaces(b)
    for kw in kws :
        if buf[pos:].lower().startswith(kw) :
            skip(b, len(kw))
            return kw

def parseVar(b) :
    """Optionally aprse a variable name, returning the name."""
    skipSpaces(b)
    if peek(b) and peek(b).isalpha() :
        s = ''
        while peek(b) and (peek(b).isalnum() or peek(b) == '_'):
            s += next(b)
        if peek(b) == '$' :
            s += next(b)
        return s

def parseStr(b) :
    """Optionally parse a string from the buffer and return it."""
    if peek(b) == '"' :
        next(b)
        s = ""
        while peek(b) and peek(b) != '"' :
            s += next(b)
        expect(b, '"')
        return s

def makeExpr(typ, **kw) :
    """Make an expression of a given type with optional extra fields"""
    e = {'exp': typ}
    for k,v in kw.items() :
        e[k] = v
    return e

def parseIntStrVar(b) :
    """Optionally parse an expression that is an integer, a string, or a variable name, returning it."""
    skipSpaces(b)
    v = parseInt(b)
    if v is not None :
        return makeExpr('int', val=v)
    v = parseStr(b)
    if v is not None :
        return makeExpr('str', val=v)
    v = parseVar(b)
    if v is not None :
        return makeExpr('var', var=v)

def parseExpr(b) :
    """Optionally parse an expression and return it."""
    # XXX add support for other operators, with precedence
    e1 = parseIntStrVar(b)
    if e1 :
        skipSpaces(b)
        if peek(b) in ['+', '-'] :
            op = next(b)
            e2 = parseExpr(b)
            e1 = makeExpr(op, e1=e1, e2=e2)
    return e1

def makeStatement(typ, **kw) :
    """Make a statement of a given type with optional extra fields"""
    st = {'text': None, 'lno': None, 'type': typ}
    for k,v in kw.items() :
        st[k] = v
    return st

def parseStatement(b) :
    """Parse a statement and return it. A statement is always returned, but it might have a type of None if there was no statement to parse."""
    skipSpaces(b)
    start = b['pos']
    kw = parseKeyword(b)
    if kw is None :
        var = parseVar(b)
        if var is None :
            st = makeStatement(None)
        else :
            # "var = expr" is a "set" alternative
            skipSpaces(b)
            expect(b, '=')
            e1 = parseExpr(b)
            require(e1)
            st = makeStatement('set', var=var, e1=e1)
    elif kw in ['new','list','run'] :
        st = makeStatement(kw)
    elif kw == 'for' :
        var = parseVar(b)
        require(var)
        skipSpaces(b)
        expect(b, '=')
        e1 = parseExpr(b)
        require(e1)
        if parseKeyword(b) != "to" :
            raise SyntaxError()
        e2 = parseExpr(b)
        require(e2)
        kw2 = parseKeyword(b)
        if kw2 is not None :
            if kw2 != 'step' :
                raise SyntaxError()
            step = parseInt(b)
        else :
            step = 1
        st = makeStatement(kw, var=var, e1=e1, e2=e2, step=step)
    elif kw == 'next' :
        var = parseVar(b) # optional
        st = makeStatement(kw, var=var)
    elif kw == 'if' :
        cond = parseExpr(b)
        require(cond)
        tst = parseStatement(b)
        require(tst)
        st = makeStatement(kw, cond=cond, st=tst)
    elif kw == 'goto' :
        targ = parseInt(b)
        require(targ)
        st = makeStatement(kw, targ=targ)
    elif kw == 'print' :
        e1 = parseExpr(b)  # optional
        skipSpaces(b)
        nl = True
        if peek(b) == ';' :
            next(b)
            nl = False
        st = makeStatement(kw, e1=e1, nl=nl)
    elif kw == 'set' :
        var = parseVar(b)
        require(var)
        skipSpaces(b)
        expect(b, '=')
        e1 = parseExpr(b)
        st = makeStatement(kw, var=var, e1=e1)
    else :
        raise SyntaxError()
    skipSpaces(b)
    ch = peek(b)
    if ch is not None and ch != ':' :
        raise SyntaxError()
    st['text'] = getParsed(b, start).strip()
    return st

# XXX currently not used
def parseStatements(b) :
    """Parse a list of statements"""
    start = b['pos']
    st = parseStatement(b)
    if peek(b) != ':' :
        return st

    sts = [st]
    while peek(b) == ':' :
        next(b)
        st = parseStatement(b)
        sts.append(st)
    st = makeStatement('block')
    st['text'] = getParsed(b, start).strip()
    return makeStatement('block')

# ------------
# Execution
# ------------

class RuntimeError(Exception) :
    pass

def evalExpr(e, vars) :
    """Evaluate an expression using the set of defined variables and return its value."""
    typ, = get(e, 'exp')
    if typ in ['int', 'str'] :
        val, = get(e, 'val')
        return val
    elif typ == 'var' :
        var = e['var']
        if var not in vars :
            # undefined variables take on their default values
            if var.endswith('$') :
                return ""
            else :
                return 0
        return vars[var]
    elif typ in ['+', '-'] :
        e1,e2 = get(e, 'e1', 'e2')
        v1 = evalExpr(e1, vars)
        v2 = evalExpr(e2, vars)
        if not isinstance(v1, int) or not isinstance(v2, int) :
            raise RuntimeError("Bad values for the %r operator: %r and %r" % (typ, v1, v2))
        if typ == '+' :
            return v1+v2
        elif typ == '-' :
            return v1-v2
    raise RuntimeError("unsupported expression %r" % typ)

def findFor(stack, var) :
    """Find the for statement in the for-stack that matches the variable and return it, leaving it on the stack. If var is None, match any for statement on the stack."""
    while stack and var != None and stack[-1]['var'] != var :
        stack.pop()
    if not stack :
        raise RuntimeError("No FOR statement for %r" % var)
    return stack[-1]

def runStatement(st, prog, vars, forstack) :
    """Run a single statement from the program, using the currently defined variables, the current program, and the current for-stack."""
    if st is None :
        return
    typ, = get(st, 'type')
    if typ == 'print' :
        e1,nl = get(st, 'e1', 'nl')
        if e1 is not None :
            v = evalExpr(e1, vars)
            if isinstance(v, int) :
                sys.stdout.write(" %d" % v)
            elif isinstance(v, str) :
                sys.stdout.write(v)
            else :
                raise RuntimeError("unspported val %r" % v)
        if nl :
            sys.stdout.write('\n')
        sys.stdout.flush()
    elif typ == 'goto' :
        lno, = get(st, 'targ')
        return lno
    elif typ == 'for' :
        var,e1 = get(st, 'var', 'e1')
        val = evalExpr(e1, vars)
        vars[var] = val
        forstack.append(st)
    elif typ == 'next' :
        var, = get(st, 'var')
        if not forstack :
            raise RuntimeError("next without for")
        forst = findFor(forstack, var)
        var2, e2,step,lno = get(forst, 'var', 'e2', 'step', 'lno')
        val = vars[var2] + step
        vars[var2] = val
        val2 = evalExpr(e2, vars)
        if val <= val2 :
            # XXX right now assume for loop is on its own line
            return nextLine(prog, lno)
        else :
            # otherwise continue as normal
            forstack.pop()
    elif typ == 'set' :
        var,e1 = get(st, 'var', 'e1')
        val = evalExpr(e1, vars)
        if var.endswith('$') :
            if not isinstance(val, str) :
                raise RuntimeError("assinging wrong value to string variable")
        else :
            if not isinstance(val, int) :
                raise RuntimeError("assinging wrong value to int variable")
        vars[var] = val
    elif typ == 'run' :
        runProg(prog, vars)
    elif typ == 'list' :
        listProg(prog)
    elif typ == 'new' :
        newProg(prog)
    else :
        raise RuntimeError("%r not yet implemented" % typ)

def lines(prog) :
    """Return line numbers in the program."""
    ls = prog.keys()
    ls.sort()
    return ls

def firstLine(prog) :
    """Return the first line number in the program if it exists."""
    ls = lines(prog)
    if ls :
        return ls[0]

def nextLine(prog, lno) :
    """Return the line after the given line number, if it exists."""
    ls = lines(prog)
    if lno not in ls :
        # this can happen if the last statement executed was "new"
        return firstLine(prog)
    idx = ls.index(lno) + 1
    if idx < len(prog) :
        return ls[idx]

def runProg(prog, vars) :
    """Run the program using the set of defined variables."""
    # should delete any existing variable bindings first
    forstack = []
    lno = firstLine(prog)
    while lno is not None :
        st = prog[lno]
        try :
            branch = runStatement(st, prog, vars, forstack)
            if branch is None :
                lno = nextLine(prog, lno)
            else :
                lno = branch
            if lno and lno not in prog :
                raise RuntimeError("can't GOTO line %d" % nextlno)
        except RuntimeError,e :
            print "%s executing: %r" % (e.message, st['text'])
            return

# -----------
# input processing, program management, and error handling
# -----------

def showError(b, start, lno, msg) :
    """Show an error message indicating where in the program it occurred."""
    buf,pos = get(b, 'buf', 'pos')
    print msg,
    if lno is not None :
        print "at line %d" % lno,
    print
    print '  "%s"' % (buf[start:])
    off = pos - start
    spaces = ' ' * off
    print '   %s^  pos %d' % (spaces, off)

def addLine(prog, st) :
    """Insert the statement into the program, or possibly delete a line if it has no statement."""
    typ,lno = get(st, 'type', 'lno')
    if typ is None :
        if lno in prog :
            del prog[lno]
        return
    prog[lno] = st

def newProg(prog) :
    """Delete all lines in the program"""
    ls = lines(prog)
    for l in ls :
        del prog[l]
    # should also delete variable bindings

def listProg(prog) :
    """Print out all the lines in the program"""
    for lno in sorted(prog.keys()) :
        st = prog[lno]
        print st['text']

# XXX need a repr where each lineno can have multiple statements
def processLine(s, prog, vars) :
    """Process a line of input, parsing it as a statement, adding it to the program if necessary, or executing it if necessary."""
    b = makeBuf(s)
    start, = get(b, 'pos')
    try :
        lno = parseInt(b) # optional
        # statements instead of statement XXX
        st = parseStatement(b) # optional
        if peek(b) is not None :
            raise SyntaxError()
    except SyntaxError :
        return showError(b, start, lno, "syntax error")

    st['lno'] = lno
    st['text'] = getParsed(b, start).strip()
    if lno is not None :
        addLine(prog, st)
    else :
        runStatement(st, prog, vars, [])
        return True

# ----------
# tests and main execution
# ----------
def testProg(src) :
    prog = {}
    vars = {}
    for l in src.split('\n') :
        l = l.strip()
        if l :
            processLine(l, prog, vars)
    if prog :
        listProg(prog)
        runProg(prog, vars)

def tests() :
    print "-- prog1"
    testProg("""
    set a = 5
    print a
    print
    """)

    print "-- prog2"
    testProg("""
    5 msg$ = "hello"
    10 print msg$;
    20 a = 0
    30 for j = 0 to 20 step 2
    35 for i = 0 to 5
    35 a = a + j
    40 print a;
    50 next 
    60 print
    """)

    print "-- prog3"
    testProg("""
    10 print 1
    20 new
    30 list
    """)

    print "-- prog4"
    testProg("""
    10 print a
    20 print x$
    """)

def interactive() :
    prog = {}
    vars = {}
    try :
        while True :
            sys.stdout.write('> ')
            sys.stdout.flush()
            l = sys.stdin.readline()
            l = l.strip()
            if l :
                if processLine(l, prog, vars) :
                    print 'READY'
    except KeyboardInterrupt :
        print "\nDONE"

def main() :
    args = sys.argv[1:]
    if args :
        for fn in args :
            if fn == 'tests' :
                tests()
            else :
                print "load", fn
                d = file(fn).read()
                testProg(d)
                print
    else :
        interactive()

if __name__ == '__main__' :
    main()

