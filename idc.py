#!/usr/bin/env python3
"""idc -- compiler for the `id` language (transpiles to C, then invokes cc).

Usage:
    idc.py PATH [-o OUTPUT] [--emit-c FILE] [--keep-c] [--cc CC]

PATH is either a single .id file (handy for tutorials) or a project directory.
A project is a directory *tree*: every directory in it may hold at most 3
entries (counting .id files and subdirectories combined), and all .id files in
the tree are compiled together as one program -- so functions and exported
variables resolve across the whole project.
"""

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

ACTION_LIMIT = 3
FUNCS_PER_FILE_LIMIT = 3
NEST_LIMIT = 2  # how deeply blocks may nest; deeper code must become a function

BASE_TYPES = {"int", "float", "string", "void"}
KEYWORDS = BASE_TYPES | {"if", "else", "while", "return", "export", "import"}

C_TYPES = {
    "int": "int",
    "float": "double",
    "string": "char*",
    "void": "void",
    "int[]": "IdList*",
    "float[]": "IdList*",
    "string[]": "IdList*",
}


def c_type(typ):
    """C type for an id type; any list type T[] is the generic IdList*."""
    if typ.endswith("[]"):
        return "IdList*"
    return C_TYPES[typ]


def box(code, typ):
    """Wrap a value of id type `typ` into a uniform list cell (long long)."""
    if typ == "int":
        return f"(long long)({code})"
    if typ == "float":
        return f"id_box_f({code})"
    return f"(long long)(intptr_t)({code})"   # string or any list (pointer)


def unbox(code, typ):
    """Read a list cell back as id type `typ`."""
    if typ == "int":
        return f"(int)({code})"
    if typ == "float":
        return f"id_unbox_f({code})"
    if typ == "string":
        return f"(char*)(intptr_t)({code})"
    return f"(IdList*)(intptr_t)({code})"     # any list type


class CompileError(Exception):
    def __init__(self, file, line, msg):
        super().__init__(f"{file}:{line}: error: {msg}")


def warn(file, line, msg):
    print(f"{file}:{line}: warning: {msg}", file=sys.stderr)


# ---------------------------------------------------------------- lexer

@dataclass
class Tok:
    kind: str   # 'int' | 'float' | 'string' | 'ident' | 'kw' | 'op' | 'eof'
    value: str
    file: str
    line: int


TOKEN_RE = re.compile(
    r"""(?P<ws>\s+)
      | (?P<comment>//[^\n]*)
      | (?P<float>\d+\.\d+)
      | (?P<int>\d+)
      | (?P<string>"(?:\\.|[^"\\])*")
      | (?P<ident>[A-Za-z_]\w*)
      | (?P<op>==|!=|<=|>=|&&|\|\||[+\-*/%<>=!(){}\[\],;])
    """,
    re.VERBOSE,
)


def lex(src: str, fname: str) -> List[Tok]:
    toks = []
    pos = 0
    line = 1
    while pos < len(src):
        m = TOKEN_RE.match(src, pos)
        if not m:
            raise CompileError(fname, line, f"unexpected character {src[pos]!r}")
        text = m.group(0)
        kind = m.lastgroup
        if kind == "ws" or kind == "comment":
            pass
        elif kind == "ident":
            if text in KEYWORDS:
                toks.append(Tok("kw", text, fname, line))
            else:
                toks.append(Tok("ident", text, fname, line))
        else:
            toks.append(Tok(kind, text, fname, line))
        line += text.count("\n")
        pos = m.end()
    toks.append(Tok("eof", "", fname, line))
    return toks


# ---------------------------------------------------------------- AST

@dataclass
class Expr:
    file: str
    line: int


@dataclass
class IntLit(Expr):
    value: str


@dataclass
class FloatLit(Expr):
    value: str


@dataclass
class StrLit(Expr):
    raw: str  # includes quotes, escapes preserved


@dataclass
class VarRef(Expr):
    name: str


@dataclass
class ImportRef(Expr):
    name: str


@dataclass
class CallExpr(Expr):
    name: str
    args: List[Expr]


@dataclass
class IndexExpr(Expr):
    base: Expr
    index: Expr


@dataclass
class ArrayLit(Expr):
    elems: List[Expr]


@dataclass
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass
class UnOp(Expr):
    op: str
    operand: Expr


@dataclass
class Stmt:
    file: str
    line: int


@dataclass
class DeclStmt(Stmt):
    typ: str
    name: str
    expr: Expr
    exported: bool


@dataclass
class AssignStmt(Stmt):
    name: str
    expr: Expr


@dataclass
class IndexAssignStmt(Stmt):
    base: Expr
    index: Expr
    expr: Expr


@dataclass
class IfStmt(Stmt):
    cond: Expr
    then: List[Stmt]
    els: Optional[object]  # List[Stmt] | IfStmt | None


@dataclass
class WhileStmt(Stmt):
    cond: Expr
    body: List[Stmt]


@dataclass
class ExprStmt(Stmt):
    expr: Expr


@dataclass
class FuncDef:
    name: str
    params: List[Tuple[str, str]]  # (type, name)
    body: List[Stmt]
    rettype: str
    retexpr: Optional[Expr]
    file: str
    line: int


# ---------------------------------------------------------------- parser

class Parser:
    def __init__(self, toks: List[Tok]):
        self.toks = toks
        self.pos = 0

    def peek(self, off=0) -> Tok:
        return self.toks[min(self.pos + off, len(self.toks) - 1)]

    def next(self) -> Tok:
        t = self.toks[self.pos]
        if t.kind != "eof":
            self.pos += 1
        return t

    def at(self, kind, value=None) -> bool:
        t = self.peek()
        return t.kind == kind and (value is None or t.value == value)

    def expect(self, kind, value=None) -> Tok:
        t = self.peek()
        if not self.at(kind, value):
            want = value if value is not None else kind
            raise CompileError(t.file, t.line, f"expected '{want}', found '{t.value or t.kind}'")
        return self.next()

    def accept(self, kind, value=None) -> bool:
        if self.at(kind, value):
            self.next()
            return True
        return False

    # -- types

    def at_type(self) -> bool:
        return self.peek().kind == "kw" and self.peek().value in BASE_TYPES

    def parse_type(self) -> str:
        t = self.expect("kw")
        if t.value not in BASE_TYPES:
            raise CompileError(t.file, t.line, f"expected a type, found '{t.value}'")
        typ = t.value
        while self.accept("op", "["):
            self.expect("op", "]")
            if typ == "void":
                raise CompileError(t.file, t.line, "'void[]' is not a valid type")
            typ += "[]"
        return typ

    # -- top level

    def parse_file(self) -> List[FuncDef]:
        funcs = []
        while not self.at("eof"):
            funcs.append(self.parse_function())
        return funcs

    def parse_function(self) -> FuncDef:
        name_tok = self.expect("ident")
        self.expect("op", "(")
        params = []
        if not self.at("op", ")"):
            while True:
                ptype = self.parse_type()
                pname = self.expect("ident")
                params.append((ptype, pname.value))
                if not self.accept("op", ","):
                    break
        self.expect("op", ")")
        body = self.parse_block()
        # the return clause lives *after* the closing brace
        rt = self.expect("kw", "return")
        if self.at("kw", "void") and not (self.peek(1).kind == "op" and self.peek(1).value == "["):
            self.next()
            rettype, retexpr = "void", None
        else:
            rettype = self.parse_type()
            retexpr = self.parse_expr()
        self.accept("op", ";")
        return FuncDef(name_tok.value, params, body, rettype, retexpr,
                       name_tok.file, name_tok.line)

    def parse_block(self) -> List[Stmt]:
        self.expect("op", "{")
        stmts = []
        while not self.at("op", "}"):
            stmts.append(self.parse_stmt())
        self.expect("op", "}")
        return stmts

    # -- statements

    def parse_stmt(self) -> Stmt:
        t = self.peek()
        if self.at("kw", "if"):
            return self.parse_if()
        if self.at("kw", "while"):
            self.next()
            self.expect("op", "(")
            cond = self.parse_expr()
            self.expect("op", ")")
            body = self.parse_block()
            return WhileStmt(t.file, t.line, cond, body)
        if self.at("kw", "export"):
            self.next()
            typ = self.parse_type()
            name = self.expect("ident")
            self.expect("op", "=")
            expr = self.parse_expr()
            self.accept("op", ";")
            return DeclStmt(t.file, t.line, typ, name.value, expr, True)
        if self.at_type():
            typ = self.parse_type()
            name = self.expect("ident")
            self.expect("op", "=")
            expr = self.parse_expr()
            self.accept("op", ";")
            return DeclStmt(t.file, t.line, typ, name.value, expr, False)
        if self.at("ident") and self.peek(1).kind == "op" and self.peek(1).value == "=":
            name = self.next()
            self.next()  # '='
            expr = self.parse_expr()
            self.accept("op", ";")
            return AssignStmt(t.file, t.line, name.value, expr)
        if self.at("ident") and self.peek(1).kind == "op" and self.peek(1).value == "[":
            target = self.parse_postfix()   # a list element: xs[i] (or xs[i][j])
            self.expect("op", "=")
            expr = self.parse_expr()
            self.accept("op", ";")
            if isinstance(target, IndexExpr):
                return IndexAssignStmt(t.file, t.line, target.base, target.index, expr)
            raise CompileError(t.file, t.line,
                               "can only assign to a variable or a list element")
        if self.at("kw", "return"):
            raise CompileError(t.file, t.line,
                               "'return' belongs after the function's closing brace")
        expr = self.parse_expr()
        self.accept("op", ";")
        return ExprStmt(t.file, t.line, expr)

    def parse_if(self) -> IfStmt:
        t = self.expect("kw", "if")
        self.expect("op", "(")
        cond = self.parse_expr()
        self.expect("op", ")")
        then = self.parse_block()
        els = None
        if self.accept("kw", "else"):
            if self.at("kw", "if"):
                els = self.parse_if()
            else:
                els = self.parse_block()
        return IfStmt(t.file, t.line, cond, then, els)

    # -- expressions (precedence climbing)
    # NOTE: a bare '=' inside an expression is equality comparison; assignment
    # is only a statement form, so there is no ambiguity.

    def parse_expr(self) -> Expr:
        return self.parse_or()

    def parse_or(self) -> Expr:
        e = self.parse_and()
        while self.at("op", "||"):
            t = self.next()
            e = BinOp(t.file, t.line, "||", e, self.parse_and())
        return e

    def parse_and(self) -> Expr:
        e = self.parse_equality()
        while self.at("op", "&&"):
            t = self.next()
            e = BinOp(t.file, t.line, "&&", e, self.parse_equality())
        return e

    def parse_equality(self) -> Expr:
        e = self.parse_relational()
        while self.at("op", "==") or self.at("op", "!=") or self.at("op", "="):
            t = self.next()
            op = "==" if t.value == "=" else t.value
            e = BinOp(t.file, t.line, op, e, self.parse_relational())
        return e

    def parse_relational(self) -> Expr:
        e = self.parse_additive()
        while self.peek().kind == "op" and self.peek().value in ("<", ">", "<=", ">="):
            t = self.next()
            e = BinOp(t.file, t.line, t.value, e, self.parse_additive())
        return e

    def parse_additive(self) -> Expr:
        e = self.parse_multiplicative()
        while self.peek().kind == "op" and self.peek().value in ("+", "-"):
            t = self.next()
            e = BinOp(t.file, t.line, t.value, e, self.parse_multiplicative())
        return e

    def parse_multiplicative(self) -> Expr:
        e = self.parse_unary()
        while self.peek().kind == "op" and self.peek().value in ("*", "/", "%"):
            t = self.next()
            e = BinOp(t.file, t.line, t.value, e, self.parse_unary())
        return e

    def parse_unary(self) -> Expr:
        t = self.peek()
        if self.at("op", "-") or self.at("op", "!"):
            self.next()
            return UnOp(t.file, t.line, t.value, self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self) -> Expr:
        e = self.parse_primary()
        while True:
            if self.at("op", "["):
                t = self.next()
                idx = self.parse_expr()
                self.expect("op", "]")
                e = IndexExpr(t.file, t.line, e, idx)
            else:
                return e

    def parse_primary(self) -> Expr:
        t = self.peek()
        if self.at("int"):
            self.next()
            return IntLit(t.file, t.line, t.value)
        if self.at("float"):
            self.next()
            return FloatLit(t.file, t.line, t.value)
        if self.at("string"):
            self.next()
            return StrLit(t.file, t.line, t.value)
        if self.at("kw", "import"):
            self.next()
            name = self.expect("ident")
            return ImportRef(t.file, t.line, name.value)
        if self.at("op", "("):
            self.next()
            e = self.parse_expr()
            self.expect("op", ")")
            return e
        if self.at("op", "["):
            self.next()
            elems = []
            if not self.at("op", "]"):
                while True:
                    elems.append(self.parse_expr())
                    if not self.accept("op", ","):
                        break
            self.expect("op", "]")
            return ArrayLit(t.file, t.line, elems)
        if self.at("ident"):
            name = self.next()
            if self.accept("op", "("):
                args = []
                if not self.at("op", ")"):
                    while True:
                        args.append(self.parse_expr())
                        if not self.accept("op", ","):
                            break
                self.expect("op", ")")
                return CallExpr(t.file, t.line, name.value, args)
            return VarRef(t.file, t.line, name.value)
        raise CompileError(t.file, t.line, f"unexpected token '{t.value or t.kind}'")


# ---------------------------------------------------------------- semantics + codegen

RUNTIME = r"""/* generated by idc -- the `id` language compiler */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>
#include <termios.h>
#include <unistd.h>
#include <time.h>

/* Growable, heap-allocated, reference-semantic list. Every element is stored
   in a uniform 8-byte cell; the compiler boxes/unboxes per the static element
   type. Because a list is a pointer, passing one to a function and mutating it
   is visible to the caller -- this is how id gets shared mutable state. */
typedef struct { int len, cap; long long* data; } IdList;
static IdList* id_list_new(void) {
    IdList* L = (IdList*)malloc(sizeof(IdList));
    L->len = 0; L->cap = 4;
    L->data = (long long*)malloc(sizeof(long long) * L->cap);
    return L;
}
static void id_list_push(IdList* L, long long v) {
    if (L->len >= L->cap) {
        L->cap *= 2;
        L->data = (long long*)realloc(L->data, sizeof(long long) * L->cap);
    }
    L->data[L->len++] = v;
}
static long long id_list_get(IdList* L, int i) {
    if (i < 0 || i >= L->len) return 0;   /* out of range -> 0 */
    return L->data[i];
}
static void id_list_set(IdList* L, int i, long long v) {
    if (i >= 0 && i < L->len) L->data[i] = v;
}
static int id_list_len(IdList* L) { return L->len; }
static long long id_list_pop(IdList* L) {   /* remove & return the last cell (0 if empty) */
    if (L->len <= 0) return 0;
    return L->data[--L->len];
}
static IdList* id_list_lit(int n, ...) {   /* elements are pre-boxed to cells */
    IdList* L = id_list_new();
    va_list ap; va_start(ap, n);
    for (int k = 0; k < n; k++) id_list_push(L, va_arg(ap, long long));
    va_end(ap);
    return L;
}
static long long id_box_f(double d) { long long x; memcpy(&x, &d, 8); return x; }
static double id_unbox_f(long long x) { double d; memcpy(&d, &x, 8); return d; }
static int id_to_int(const char* s) { return atoi(s); }

static char* id_concat(const char* a, const char* b) {
    size_t la = strlen(a), lb = strlen(b);
    char* r = (char*)malloc(la + lb + 1);
    memcpy(r, a, la);
    memcpy(r + la, b, lb + 1);
    return r;
}
static char* id_str_of_int(int x) {
    char* r = (char*)malloc(32); snprintf(r, 32, "%d", x); return r;
}
static char* id_str_of_float(double x) {
    char* r = (char*)malloc(64); snprintf(r, 64, "%g", x); return r;
}
static void id_print(const char* s) { puts(s); }
static char* id_input(void) {
    /* read one line from stdin, drop the trailing newline; "" on EOF */
    char buf[1024];
    if (!fgets(buf, sizeof(buf), stdin)) {
        char* e = (char*)malloc(1); e[0] = '\0'; return e;
    }
    size_t n = strlen(buf);
    if (n > 0 && buf[n - 1] == '\n') { buf[--n] = '\0'; }
    char* r = (char*)malloc(n + 1); memcpy(r, buf, n + 1); return r;
}
static char* id_read_all(void) {
    /* slurp all of stdin into one string (grows as needed) */
    size_t cap = 4096, n = 0;
    char* r = (char*)malloc(cap);
    for (;;) {
        if (n + 1 >= cap) { cap *= 2; r = (char*)realloc(r, cap); }
        size_t got = fread(r + n, 1, cap - n - 1, stdin);
        n += got;
        if (got == 0) break;
    }
    r[n] = '\0';
    return r;
}
static int id_len(const char* s) { return (int)strlen(s); }
static int id_charat(const char* s, int i) {
    if (i < 0 || i >= (int)strlen(s)) return -1;   /* out of range -> -1 */
    return (unsigned char)s[i];
}
static char* id_chr(int code) {
    char* r = (char*)malloc(2);
    r[0] = (char)code; r[1] = '\0';
    return r;
}

/* real-time terminal I/O: write without a newline, flush, poll a single key
   without blocking (raw mode is entered lazily and restored at exit), and
   sleep. Together these let id drive an animated full-screen frame loop. */
static void id_put(const char* s) { fputs(s, stdout); }
static void id_flush(void) { fflush(stdout); }
static struct termios id_saved_termios;
static int id_raw_active = 0;
static void id_term_restore(void) {
    if (id_raw_active) {
        tcsetattr(STDIN_FILENO, TCSANOW, &id_saved_termios);
        id_raw_active = 0;
    }
}
static void id_term_raw(void) {
    struct termios t;
    if (id_raw_active) return;
    if (tcgetattr(STDIN_FILENO, &id_saved_termios) != 0) return;
    t = id_saved_termios;
    t.c_lflag &= ~(tcflag_t)(ICANON | ECHO);
    t.c_cc[VMIN] = 0; t.c_cc[VTIME] = 0;   /* read() returns at once, 0 on no key */
    tcsetattr(STDIN_FILENO, TCSANOW, &t);
    id_raw_active = 1;
    atexit(id_term_restore);
}
static int id_getkey(void) {
    unsigned char c;
    id_term_raw();
    if (read(STDIN_FILENO, &c, 1) == 1) return (int)c;
    return -1;   /* no key available this poll */
}
static void id_sleep_ms(int ms) {
    struct timespec ts;
    if (ms < 0) ms = 0;
    ts.tv_sec = ms / 1000;
    ts.tv_nsec = (long)(ms % 1000) * 1000000L;
    nanosleep(&ts, NULL);
}
static int id_ticks(void) {   /* monotonic milliseconds, for timing and seeding */
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}
"""


def is_numeric(t):
    return t in ("int", "float")


def compatible(want, got):
    if want == got:
        return True
    return is_numeric(want) and is_numeric(got)


class Compiler:
    def __init__(self, funcs_by_file):
        self.funcs = {}            # name -> FuncDef
        self.exported = {}         # name -> (type, owner fn name)
        self.var_owner = {}        # var name -> (fn name, file, line)
        self.unknown_fns = {}      # name -> (file, line) of first call
        self.lines = []

        for fname, funcs in funcs_by_file.items():
            if len(funcs) > FUNCS_PER_FILE_LIMIT:
                f = funcs[FUNCS_PER_FILE_LIMIT]
                raise CompileError(f.file, f.line,
                                   f"too many functions in this file ({len(funcs)}); "
                                   f"the limit is {FUNCS_PER_FILE_LIMIT} per file")
            for fn in funcs:
                if fn.name in self.funcs:
                    prev = self.funcs[fn.name]
                    raise CompileError(fn.file, fn.line,
                                       f"function '{fn.name}' already defined at "
                                       f"{prev.file}:{prev.line}")
                self.funcs[fn.name] = fn

        self.var_types = {}        # non-exported name -> its single type

        # pass 1: claim exported names (these become reserved globals)
        for fn in self.funcs.values():
            for stmt in walk_stmts(fn.body):
                if isinstance(stmt, DeclStmt) and stmt.exported:
                    if stmt.name in self.exported:
                        owner = self.exported[stmt.name][1]
                        raise CompileError(stmt.file, stmt.line,
                                           f"'{stmt.name}' is already an exported "
                                           f"global (exported by '{owner}')")
                    self.exported[stmt.name] = (stmt.typ, fn.name)

        # pass 2: every variable declaration. A name may repeat across functions
        # only if it always has the same type; an exported name is reserved and
        # cannot be reused by any other variable.
        for fn in self.funcs.values():
            seen = set()
            for ptype, pname in fn.params:
                self.register_var(pname, ptype, fn, fn.file, fn.line, False, seen)
            for stmt in walk_stmts(fn.body):
                if isinstance(stmt, DeclStmt):
                    self.register_var(stmt.name, stmt.typ, fn, stmt.file, stmt.line,
                                      stmt.exported, seen)

    def register_var(self, name, typ, fn, file, line, exported, seen):
        if name in self.funcs:
            raise CompileError(file, line,
                               f"'{name}' is already the name of a function")
        if name in seen:
            raise CompileError(file, line,
                               f"variable '{name}' is declared twice in function "
                               f"'{fn.name}'")
        seen.add(name)
        if name in self.exported and not exported:
            owner = self.exported[name][1]
            raise CompileError(file, line,
                               f"'{name}' is an exported global (by '{owner}'); "
                               f"another variable cannot reuse that name -- read "
                               f"the global with 'import {name}'")
        if not exported:
            if name in self.var_types and self.var_types[name] != typ:
                raise CompileError(file, line,
                                   f"variable '{name}' is declared {typ} here but "
                                   f"{self.var_types[name]} elsewhere; a name must "
                                   f"keep one type across the whole program")
            self.var_types[name] = typ
        self.var_owner.setdefault(name, (fn.name, file, line))

    # -- entry point

    def check_unique_functions(self):
        seen = {}  # canonical fingerprint -> the first function with it
        for fn in self.funcs.values():
            key = canonical_function(fn)
            if key in seen:
                orig = seen[key]
                raise CompileError(
                    fn.file, fn.line,
                    f"function '{fn.name}' has the same signature and logic as "
                    f"'{orig.name}' (defined at {orig.file}:{orig.line}); functions "
                    f"must be unique -- remove one and call it from both places, or "
                    f"make them genuinely differ")
            seen[key] = fn

    def compile(self) -> str:
        self.check_unique_functions()
        bodies = []
        for fn in self.funcs.values():
            self.check_action_limit(fn)
            bodies.append(self.gen_function(fn))

        out = [RUNTIME]

        if self.unknown_fns:
            out.append("/* functions not defined in any input file (resolved at link time) */")
            for name in self.unknown_fns:
                out.append(f"extern int id_{name}();")
            out.append("")

        out.append("/* forward declarations */")
        for fn in self.funcs.values():
            out.append(self.signature(fn) + ";")
        out.append("")

        if self.exported:
            out.append("/* exported variables */")
            for name, (typ, owner) in self.exported.items():
                out.append(f"{self.c_decl(typ, name)};  /* exported by {owner}() */")
            out.append("")

        out.extend(bodies)
        out.append(self.gen_entrypoint())
        return "\n".join(out) + "\n"

    # -- the 3-action rule: EVERY block (the function body and the body of each
    #    if/else/while) may perform at most 3 actions. Each statement is one
    #    action; an `if` is one and each chained `else` is another; a `while` is
    #    one. The return clause is free. Blocks may also nest only NEST_LIMIT
    #    deep -- code below that must be split into its own function.

    def block_actions(self, body) -> int:
        n = 0
        for s in body:
            if isinstance(s, IfStmt):
                n += 1
                cur = s.els
                while cur is not None:
                    n += 1  # each `else` (or `else if`) is an action
                    cur = cur.els if isinstance(cur, IfStmt) else None
            else:
                n += 1
        return n

    def check_action_limit(self, fn: FuncDef):
        self.check_block(fn.body, 0, fn, fn.file, fn.line)

    def check_block(self, body, depth, fn, file, line):
        if depth > NEST_LIMIT:
            raise CompileError(file, line,
                               f"code in '{fn.name}' is nested too deeply "
                               f"({depth} levels); the maximum is {NEST_LIMIT}. "
                               f"Split the inner block into its own function")
        n = self.block_actions(body)
        if n > ACTION_LIMIT:
            raise CompileError(file, line,
                               f"a block in '{fn.name}' performs {n} actions; the "
                               f"limit is {ACTION_LIMIT} (each statement, if, else, "
                               f"and while is one action; return is free)")
        for s in body:
            if isinstance(s, IfStmt):
                cur = s
                while isinstance(cur, IfStmt):  # walk an if / else-if chain
                    self.check_block(cur.then, depth + 1, fn, cur.file, cur.line)
                    cur = cur.els
                if cur is not None:             # trailing plain `else` block
                    self.check_block(cur, depth + 1, fn, s.file, s.line)
            elif isinstance(s, WhileStmt):
                self.check_block(s.body, depth + 1, fn, s.file, s.line)

    # -- codegen helpers

    def c_decl(self, typ, name):
        return f"{c_type(typ)} {name}"

    def signature(self, fn: FuncDef) -> str:
        ps = ", ".join(self.c_decl(t, n) for t, n in fn.params) or "void"
        return f"{c_type(fn.rettype)} id_{fn.name}({ps})"

    def gen_function(self, fn: FuncDef) -> str:
        lines = [self.signature(fn) + " {"]
        env = {pname: ptype for ptype, pname in fn.params}

        # hoist local declarations to function scope: variables are
        # function-scoped (the trailing return clause may reference them)
        hoisted = []
        for stmt in walk_stmts(fn.body):
            if isinstance(stmt, DeclStmt):
                env[stmt.name] = stmt.typ
                if not stmt.exported:
                    hoisted.append(f"    {self.c_decl(stmt.typ, stmt.name)};")
        lines.extend(hoisted)

        for stmt in fn.body:
            lines.extend(self.gen_stmt(stmt, fn, env, 1))

        if fn.rettype == "void":
            lines.append("    return;")
        else:
            code, typ = self.gen_expr(fn.retexpr, fn, env, fn.rettype)
            if not compatible(fn.rettype, typ):
                raise CompileError(fn.retexpr.file, fn.retexpr.line,
                                   f"function '{fn.name}' returns {fn.rettype} but "
                                   f"the expression has type {typ}")
            lines.append(f"    return {code};")
        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    def gen_stmt(self, stmt, fn, env, depth) -> List[str]:
        ind = "    " * depth
        if isinstance(stmt, DeclStmt):
            code, typ = self.gen_expr(stmt.expr, fn, env, stmt.typ)
            if not compatible(stmt.typ, typ):
                raise CompileError(stmt.file, stmt.line,
                                   f"cannot initialize {stmt.typ} '{stmt.name}' "
                                   f"with a {typ} value")
            return [f"{ind}{stmt.name} = {code};"]
        if isinstance(stmt, AssignStmt):
            if stmt.name not in env:
                self.explain_bad_var(stmt.name, fn, stmt.file, stmt.line)
            code, typ = self.gen_expr(stmt.expr, fn, env, env[stmt.name])
            if not compatible(env[stmt.name], typ):
                raise CompileError(stmt.file, stmt.line,
                                   f"cannot assign a {typ} value to "
                                   f"{env[stmt.name]} '{stmt.name}'")
            return [f"{ind}{stmt.name} = {code};"]
        if isinstance(stmt, IndexAssignStmt):
            base, btyp = self.gen_expr(stmt.base, fn, env)
            if not btyp.endswith("[]"):
                raise CompileError(stmt.file, stmt.line, f"cannot index a {btyp}")
            idx, ityp = self.gen_expr(stmt.index, fn, env)
            if ityp != "int":
                raise CompileError(stmt.file, stmt.line,
                                   f"list index must be int, got {ityp}")
            elem = btyp[:-2]
            code, typ = self.gen_expr(stmt.expr, fn, env, elem)
            if not compatible(elem, typ):
                raise CompileError(stmt.file, stmt.line,
                                   f"cannot store a {typ} into a {btyp}")
            return [f"{ind}id_list_set({base}, {idx}, {box(code, elem)});"]
        if isinstance(stmt, IfStmt):
            cond, ctyp = self.gen_expr(stmt.cond, fn, env)
            if ctyp == "void":
                raise CompileError(stmt.file, stmt.line, "condition has type void")
            out = [f"{ind}if ({cond}) {{"]
            for s in stmt.then:
                out.extend(self.gen_stmt(s, fn, env, depth + 1))
            out.append(f"{ind}}}")
            if stmt.els is not None:
                if isinstance(stmt.els, IfStmt):
                    else_lines = self.gen_stmt(stmt.els, fn, env, depth)
                    out[-1] = f"{ind}}} else " + else_lines[0].lstrip()
                    out.extend(else_lines[1:])
                else:
                    out[-1] = f"{ind}}} else {{"
                    for s in stmt.els:
                        out.extend(self.gen_stmt(s, fn, env, depth + 1))
                    out.append(f"{ind}}}")
            return out
        if isinstance(stmt, WhileStmt):
            cond, ctyp = self.gen_expr(stmt.cond, fn, env)
            if ctyp == "void":
                raise CompileError(stmt.file, stmt.line, "loop condition has type void")
            out = [f"{ind}while ({cond}) {{"]
            for s in stmt.body:
                out.extend(self.gen_stmt(s, fn, env, depth + 1))
            out.append(f"{ind}}}")
            return out
        if isinstance(stmt, ExprStmt):
            code, _ = self.gen_expr(stmt.expr, fn, env)
            return [f"{ind}{code};"]
        raise AssertionError(stmt)

    def explain_bad_var(self, name, fn, file, line):
        if name in self.var_owner:
            owner = self.var_owner[name][0]
            if name in self.exported:
                raise CompileError(file, line,
                                   f"variable '{name}' belongs to function '{owner}'; "
                                   f"read it with 'import {name}'")
            raise CompileError(file, line,
                               f"variable '{name}' belongs to function '{owner}' and "
                               f"is not exported; variables are only globally "
                               f"accessible if export/import is used")
        raise CompileError(file, line, f"undefined variable '{name}'")

    # -- expressions: returns (c_code, id_type)

    def gen_expr(self, e, fn, env, expected=None) -> Tuple[str, str]:
        if isinstance(e, IntLit):
            return e.value, "int"
        if isinstance(e, FloatLit):
            return e.value, "float"
        if isinstance(e, StrLit):
            return e.raw, "string"
        if isinstance(e, VarRef):
            if e.name not in env:
                self.explain_bad_var(e.name, fn, e.file, e.line)
            return e.name, env[e.name]
        if isinstance(e, ImportRef):
            if e.name not in self.exported:
                if e.name in self.var_owner:
                    owner = self.var_owner[e.name][0]
                    raise CompileError(e.file, e.line,
                                       f"variable '{e.name}' (in function '{owner}') "
                                       f"is not exported")
                raise CompileError(e.file, e.line,
                                   f"no exported variable named '{e.name}'")
            return e.name, self.exported[e.name][0]
        if isinstance(e, IndexExpr):
            base, btyp = self.gen_expr(e.base, fn, env)
            if not btyp.endswith("[]"):
                raise CompileError(e.file, e.line, f"cannot index a {btyp}")
            idx, ityp = self.gen_expr(e.index, fn, env)
            if ityp != "int":
                raise CompileError(e.file, e.line, f"array index must be int, got {ityp}")
            elem = btyp[:-2]
            return unbox(f"id_list_get({base}, {idx})", elem), elem
        if isinstance(e, ArrayLit):
            if not e.elems:
                if expected is None or not expected.endswith("[]"):
                    raise CompileError(e.file, e.line,
                                       "an empty list literal needs a known list "
                                       "type here (e.g. on a typed declaration)")
                return "id_list_lit(0)", expected
            raw, etyp = [], None
            for el in e.elems:
                code, typ = self.gen_expr(el, fn, env)
                if etyp is None:
                    etyp = typ
                elif not compatible(etyp, typ):
                    raise CompileError(el.file, el.line,
                                       f"list element has type {typ}, expected {etyp}")
                if is_numeric(etyp) and typ == "float":
                    etyp = "float"
                raw.append(code)
            cells = ", ".join(box(c, etyp) for c in raw)
            return f"id_list_lit({len(raw)}, {cells})", etyp + "[]"
        if isinstance(e, CallExpr):
            return self.gen_call(e, fn, env)
        if isinstance(e, UnOp):
            code, typ = self.gen_expr(e.operand, fn, env)
            if e.op == "-" and not is_numeric(typ):
                raise CompileError(e.file, e.line, f"cannot negate a {typ}")
            if e.op == "!" and typ != "int":
                raise CompileError(e.file, e.line, f"cannot apply '!' to a {typ}")
            return f"({e.op}{code})", typ
        if isinstance(e, BinOp):
            return self.gen_binop(e, fn, env)
        raise AssertionError(e)

    def gen_call(self, e: CallExpr, fn, env) -> Tuple[str, str]:
        if e.name == "print":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "print takes exactly one argument")
            code, typ = self.gen_expr(e.args[0], fn, env)
            return f"id_print({self.to_string(code, typ, e)})", "void"
        if e.name == "input":
            if len(e.args) != 0:
                raise CompileError(e.file, e.line, "input takes no arguments")
            return "id_input()", "string"
        if e.name == "read_all":
            if len(e.args) != 0:
                raise CompileError(e.file, e.line, "read_all takes no arguments")
            return "id_read_all()", "string"
        if e.name == "len":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "len takes exactly one argument")
            code, typ = self.gen_expr(e.args[0], fn, env)
            if typ == "string":
                return f"id_len({code})", "int"
            if typ.endswith("[]"):
                return f"id_list_len({code})", "int"
            raise CompileError(e.file, e.line,
                               f"len expects a string or list, got {typ}")
        if e.name == "push":
            if len(e.args) != 2:
                raise CompileError(e.file, e.line, "push takes exactly two arguments")
            lc, lt = self.gen_expr(e.args[0], fn, env)
            if not lt.endswith("[]"):
                raise CompileError(e.file, e.line, f"push expects a list, got {lt}")
            elem = lt[:-2]
            vc, vt = self.gen_expr(e.args[1], fn, env, elem)
            if not compatible(elem, vt):
                raise CompileError(e.file, e.line,
                                   f"cannot push a {vt} onto a {lt}")
            return f"id_list_push({lc}, {box(vc, elem)})", "void"
        if e.name == "pop":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "pop takes exactly one argument")
            lc, lt = self.gen_expr(e.args[0], fn, env)
            if not lt.endswith("[]"):
                raise CompileError(e.file, e.line, f"pop expects a list, got {lt}")
            elem = lt[:-2]
            return unbox(f"id_list_pop({lc})", elem), elem
        if e.name == "to_int":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "to_int takes exactly one argument")
            code, typ = self.gen_expr(e.args[0], fn, env)
            if typ != "string":
                raise CompileError(e.file, e.line, f"to_int expects a string, got {typ}")
            return f"id_to_int({code})", "int"
        if e.name == "charat":
            if len(e.args) != 2:
                raise CompileError(e.file, e.line, "charat takes exactly two arguments")
            sc, st = self.gen_expr(e.args[0], fn, env)
            ic, it = self.gen_expr(e.args[1], fn, env)
            if st != "string":
                raise CompileError(e.file, e.line, f"charat expects a string, got {st}")
            if it != "int":
                raise CompileError(e.file, e.line, f"charat index must be int, got {it}")
            return f"id_charat({sc}, {ic})", "int"
        if e.name == "chr":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "chr takes exactly one argument")
            code, typ = self.gen_expr(e.args[0], fn, env)
            if typ != "int":
                raise CompileError(e.file, e.line, f"chr expects an int, got {typ}")
            return f"id_chr({code})", "string"
        if e.name == "put":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "put takes exactly one argument")
            code, typ = self.gen_expr(e.args[0], fn, env)
            return f"id_put({self.to_string(code, typ, e)})", "void"
        if e.name == "flush":
            if len(e.args) != 0:
                raise CompileError(e.file, e.line, "flush takes no arguments")
            return "id_flush()", "void"
        if e.name == "getkey":
            if len(e.args) != 0:
                raise CompileError(e.file, e.line, "getkey takes no arguments")
            return "id_getkey()", "int"
        if e.name == "sleep_ms":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "sleep_ms takes exactly one argument")
            code, typ = self.gen_expr(e.args[0], fn, env)
            if typ != "int":
                raise CompileError(e.file, e.line, f"sleep_ms expects an int, got {typ}")
            return f"id_sleep_ms({code})", "void"
        if e.name == "ticks":
            if len(e.args) != 0:
                raise CompileError(e.file, e.line, "ticks takes no arguments")
            return "id_ticks()", "int"
        args = [self.gen_expr(a, fn, env) for a in e.args]
        callee = self.funcs.get(e.name)
        if callee is None:
            if e.name in self.var_owner:
                raise CompileError(e.file, e.line, f"'{e.name}' is a variable, not a function")
            if e.name not in self.unknown_fns:
                warn(e.file, e.line,
                     f"call to function '{e.name}' which is not defined in any input "
                     f"file; it must be provided at link time")
                self.unknown_fns[e.name] = (e.file, e.line)
            return f"id_{e.name}({', '.join(c for c, _ in args)})", "int"
        if len(args) != len(callee.params):
            raise CompileError(e.file, e.line,
                               f"function '{e.name}' takes {len(callee.params)} "
                               f"argument(s), got {len(args)}")
        for (ptype, pname), (code, typ), arg in zip(callee.params, args, e.args):
            if not compatible(ptype, typ):
                raise CompileError(arg.file, arg.line,
                                   f"argument '{pname}' of '{e.name}' expects "
                                   f"{ptype}, got {typ}")
        return f"id_{e.name}({', '.join(c for c, _ in args)})", callee.rettype

    def to_string(self, code, typ, e) -> str:
        if typ == "string":
            return code
        if typ == "int":
            return f"id_str_of_int({code})"
        if typ == "float":
            return f"id_str_of_float({code})"
        raise CompileError(e.file, e.line, f"cannot convert {typ} to string")

    def gen_binop(self, e: BinOp, fn, env) -> Tuple[str, str]:
        lc, lt = self.gen_expr(e.left, fn, env)
        rc, rt = self.gen_expr(e.right, fn, env)
        op = e.op
        if op == "+" and (lt == "string" or rt == "string"):
            return (f"id_concat({self.to_string(lc, lt, e.left)}, "
                    f"{self.to_string(rc, rt, e.right)})"), "string"
        if op in ("==", "!="):
            if lt == "string" and rt == "string":
                return f"(strcmp({lc}, {rc}) {op} 0)", "int"
            if is_numeric(lt) and is_numeric(rt):
                return f"({lc} {op} {rc})", "int"
            raise CompileError(e.file, e.line, f"cannot compare {lt} with {rt}")
        if op in ("<", "<=", ">", ">="):
            if is_numeric(lt) and is_numeric(rt):
                return f"({lc} {op} {rc})", "int"
            raise CompileError(e.file, e.line, f"cannot order {lt} and {rt}")
        if op in ("&&", "||"):
            if lt == "int" and rt == "int":
                return f"({lc} {op} {rc})", "int"
            raise CompileError(e.file, e.line, f"'{op}' requires int operands")
        if op in ("+", "-", "*", "/", "%"):
            if is_numeric(lt) and is_numeric(rt):
                if op == "%" and (lt == "float" or rt == "float"):
                    raise CompileError(e.file, e.line, "'%' requires int operands")
                res = "float" if "float" in (lt, rt) else "int"
                return f"({lc} {op} {rc})", res
            raise CompileError(e.file, e.line, f"cannot apply '{op}' to {lt} and {rt}")
        raise AssertionError(op)

    # -- C entrypoint wrapper around the id main()

    def gen_entrypoint(self) -> str:
        m = self.funcs.get("main")
        if m is None:
            return ""
        ptypes = [t for t, _ in m.params]
        prelude = ""
        if ptypes == ["int", "string[]"]:
            # marshal C argv (char**) into an id string[] list
            prelude = ("IdList* id_args = id_list_new();\n"
                       "    for (int i = 0; i < argc; i++)\n"
                       "        id_list_push(id_args, (long long)(intptr_t)argv[i]);\n    ")
            call = "id_main(argc, id_args)"
        elif ptypes == []:
            call = "id_main()"
        else:
            raise CompileError(m.file, m.line,
                               "main must take (int, string[]) or no parameters")
        if m.rettype == "int":
            body = f"return {call};"
        else:
            body = f"{call}; return 0;"
        return (f"int main(int argc, char** argv) {{ (void)argc; (void)argv;\n    "
                f"{prelude}{body} }}\n")


def walk_stmts(body):
    """Yield every statement, including those nested in if/else blocks."""
    for s in body:
        yield s
        if isinstance(s, IfStmt):
            yield from walk_stmts(s.then)
            if isinstance(s.els, IfStmt):
                yield from walk_stmts([s.els])
            elif s.els:
                yield from walk_stmts(s.els)
        elif isinstance(s, WhileStmt):
            yield from walk_stmts(s.body)


# -- function uniqueness -------------------------------------------------------
# Two functions that are identical except for their name are duplicate
# functionality and a compile error. We fingerprint each function by its
# signature (parameter types + return type) and the structure of its body, with
# the function's own parameters and locals alpha-normalized (v0, v1, ...) so a
# mere renaming can't hide a duplicate. What stays verbatim carries real meaning:
# operators, literals, the names of called functions and builtins, imported and
# exported global names. A self-recursive call is normalized to `self`, so two
# identical recursive functions also collide.

def _canon_expr(e, cn, selfname):
    if isinstance(e, IntLit):
        return "I" + e.value
    if isinstance(e, FloatLit):
        return "F" + e.value
    if isinstance(e, StrLit):
        return "S" + e.raw
    if isinstance(e, VarRef):
        return "v" + cn(e.name)
    if isinstance(e, ImportRef):
        return "g(" + e.name + ")"
    if isinstance(e, CallExpr):
        callee = "self" if e.name == selfname else e.name
        return "c(" + callee + ":" + ",".join(_canon_expr(a, cn, selfname) for a in e.args) + ")"
    if isinstance(e, IndexExpr):
        return "ix(" + _canon_expr(e.base, cn, selfname) + "," + _canon_expr(e.index, cn, selfname) + ")"
    if isinstance(e, ArrayLit):
        return "ar(" + ",".join(_canon_expr(x, cn, selfname) for x in e.elems) + ")"
    if isinstance(e, BinOp):
        return "b" + e.op + "(" + _canon_expr(e.left, cn, selfname) + "," + _canon_expr(e.right, cn, selfname) + ")"
    if isinstance(e, UnOp):
        return "u" + e.op + "(" + _canon_expr(e.operand, cn, selfname) + ")"
    raise AssertionError(e)


def _canon_stmt(s, cn, selfname):
    if isinstance(s, DeclStmt):
        if s.exported:   # exported name is a reserved global -> keep it verbatim
            return "ed:" + s.typ + " " + s.name + "=" + _canon_expr(s.expr, cn, selfname)
        return "d:" + s.typ + " " + cn(s.name) + "=" + _canon_expr(s.expr, cn, selfname)
    if isinstance(s, AssignStmt):
        return "a:" + cn(s.name) + "=" + _canon_expr(s.expr, cn, selfname)
    if isinstance(s, IndexAssignStmt):
        return ("ia:" + _canon_expr(s.base, cn, selfname) + "[" +
                _canon_expr(s.index, cn, selfname) + "]=" + _canon_expr(s.expr, cn, selfname))
    if isinstance(s, IfStmt):
        out = "if(" + _canon_expr(s.cond, cn, selfname) + "){" + _canon_block(s.then, cn, selfname) + "}"
        if isinstance(s.els, IfStmt):
            out += "elif" + _canon_stmt(s.els, cn, selfname)
        elif s.els:
            out += "else{" + _canon_block(s.els, cn, selfname) + "}"
        return out
    if isinstance(s, WhileStmt):
        return "wh(" + _canon_expr(s.cond, cn, selfname) + "){" + _canon_block(s.body, cn, selfname) + "}"
    if isinstance(s, ExprStmt):
        return "e:" + _canon_expr(s.expr, cn, selfname)
    raise AssertionError(s)


def _canon_block(body, cn, selfname):
    return ";".join(_canon_stmt(s, cn, selfname) for s in body)


def canonical_function(fn):
    """A signature+logic fingerprint of a function, independent of its name and
    of how it spells its own parameters and locals."""
    names = {}

    def cn(n):
        if n not in names:
            names[n] = str(len(names))
        return names[n]

    params = ",".join(ptype + " " + cn(pname) for ptype, pname in fn.params)
    body = _canon_block(fn.body, cn, fn.name)
    ret = "void" if fn.retexpr is None else _canon_expr(fn.retexpr, cn, fn.name)
    return "(" + params + ")->" + fn.rettype + "{" + body + "}=>" + ret


# ---------------------------------------------------------------- driver

# A project is a directory tree. To keep it unified and uncluttered, every
# directory in it may hold at most 3 entries, counting .id files and
# subdirectories (other files, e.g. docs, are ignored and don't count). idc
# compiles all .id files in the tree, in a deterministic sorted-path order.
PROJECT_ENTRY_LIMIT = 3


def collect_project(root):
    """Walk the project tree, enforce the per-directory entry limit, and return
    every .id file in deterministic (sorted full-path) order."""
    id_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # ignore hidden entries; they neither compile nor count
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        ids = [n for n in filenames if n.endswith(".id")]
        entries = len(ids) + len(dirnames)
        if entries > PROJECT_ENTRY_LIMIT:
            raise CompileError(
                dirpath, 1,
                f"a project directory may contain at most {PROJECT_ENTRY_LIMIT} "
                f"files and directories combined, but this one has {entries} "
                f"(.id files and subdirectories); split it into subdirectories")
        id_files.extend(os.path.join(dirpath, n) for n in ids)
    if not id_files:
        raise CompileError(root, 1, "no .id files in this project")
    id_files.sort()
    return id_files


def main(argv):
    ap = argparse.ArgumentParser(prog="idc", description="compiler for the id language")
    ap.add_argument("path",
                    help="a single .id file, or a project directory (its whole "
                         "tree of .id files is compiled together)")
    ap.add_argument("-o", "--output", help="output executable path")
    ap.add_argument("--emit-c", metavar="FILE", help="write the generated C and stop")
    ap.add_argument("--keep-c", action="store_true",
                    help="keep the generated C next to the output")
    ap.add_argument("--cc", default="cc", help="C compiler to use (default: cc)")
    args = ap.parse_args(argv)

    try:
        if os.path.isdir(args.path):
            source_files = collect_project(args.path)
        elif os.path.isfile(args.path):
            source_files = [args.path]
        else:
            print(f"idc: no such file or directory: '{args.path}'", file=sys.stderr)
            return 1

        funcs_by_file = {}
        for path in source_files:
            with open(path) as f:
                src = f.read()
            funcs_by_file[path] = Parser(lex(src, path)).parse_file()
        compiler = Compiler(funcs_by_file)
        c_code = compiler.compile()
    except CompileError as err:
        print(str(err), file=sys.stderr)
        return 1
    except OSError as err:
        print(f"idc: {err}", file=sys.stderr)
        return 1

    if args.emit_c:
        with open(args.emit_c, "w") as f:
            f.write(c_code)
        print(f"wrote {args.emit_c}")
        return 0

    have_main = "main" in compiler.funcs
    out = args.output
    if out is None:
        # default name: the project directory's name, or the file's stem
        first = os.path.normpath(args.path)
        base = os.path.basename(first if os.path.isdir(first)
                                else os.path.splitext(first)[0])
        out = base + (".o" if not have_main else "")

    c_path = (os.path.splitext(out)[0] + ".c") if args.keep_c else out + ".gen.c"
    with open(c_path, "w") as f:
        f.write(c_code)

    cmd = [args.cc, "-std=c11", "-O2", c_path, "-o", out]
    if not have_main:
        cmd.insert(1, "-c")  # no entrypoint: produce an object file to link later
    try:
        res = subprocess.run(cmd)
    finally:
        if not args.keep_c:
            os.unlink(c_path)
    if res.returncode != 0:
        print(f"idc: C compilation failed (command: {' '.join(cmd)})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
