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
import difflib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

ACTION_LIMIT = 3
FUNCS_PER_FILE_LIMIT = 3
NEST_LIMIT = 2  # how deeply blocks may nest; deeper code must become a function

# The complete list of `id` builtins, in the order they should be advertised to
# users -- kept in exactly one place so the "did you mean" hint and the
# "available builtins" listing (used when a call resolves to neither a
# defined function nor a builtin) can never drift from what the backends
# actually implement.
BUILTIN_NAMES = (
    "print", "input", "read_all", "len", "push", "pop", "to_int", "charat",
    "chr", "put", "flush", "getkey", "sleep_ms", "ticks",
)

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


def builtin_hint(name) -> str:
    """' did you mean the builtin '<X>'?' if `name` is a close match to a
    known builtin, else ''. Shared by every diagnostic about a call to a
    name that isn't a defined function or a builtin."""
    matches = difflib.get_close_matches(name, BUILTIN_NAMES, n=1)
    return f" did you mean the builtin '{matches[0]}'?" if matches else ""


def no_such_function_msg(name) -> str:
    """The full diagnostic for a call to a name that resolves to neither a
    defined function nor a builtin: the "did you mean" hint (if any) plus
    the complete list of builtins, so users guessing at a name (e.g.
    `char_at` for `charat`) get pointed at the real one instead of a bare
    linker error further down the pipeline."""
    return (f"no such function '{name}';{builtin_hint(name)} "
            f"available builtins: {', '.join(BUILTIN_NAMES)}")


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

    # Human phrases for token *kinds*, used when a KIND (not a specific
    # literal value) was expected -- newcomers can't decode raw kind names
    # like 'kw' or 'op'.
    KIND_PHRASES = {
        "kw": "a keyword",
        "ident": "an identifier (a name)",
        "op": "an operator",
        "int": "an integer literal",
        "float": "a float literal",
        "string": "a string literal",
        "eof": "end of input",
    }

    def expect(self, kind, value=None, what=None) -> Tok:
        t = self.peek()
        if not self.at(kind, value):
            if value is not None:
                want = f"'{value}'"
            else:
                want = what if what is not None else self.KIND_PHRASES.get(kind, kind)
            raise CompileError(t.file, t.line, f"expected {want}, found '{t.value or t.kind}'")
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
        t = self.expect("kw", what="a type (int, string, void, or a T[] array type)")
        if t.value not in BASE_TYPES:
            raise CompileError(t.file, t.line,
                                f"expected a type (int, string, void, or a T[] array type), found '{t.value}'")
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
#include <limits.h>
#include <termios.h>
#include <unistd.h>
#include <time.h>

/* ---- allocation arena -----------------------------------------------------
   Every heap block the runtime allocates (list headers/cells, and the C
   strings built by concat/str_of_int/str_of_float/input/read_all/chr) is
   wrapped with a small intrusive header and linked into one list, so the
   whole arena can be released in a single pass at process exit (the free-all
   is registered with atexit on the first allocation). id programs never call
   free() themselves, so without this a long-running program (e.g. string
   concatenation in a loop) would leak every intermediate string forever;
   with it, nothing outlives the process. This bounds *leaks*, not *peak*
   memory during the run -- a program that builds one huge string still holds
   every intermediate allocation live until exit, same as before this change.
   Every allocation in this file goes through id_alloc/id_realloc below, which
   also check for allocation failure and for size-computation overflow,
   aborting with a clear message instead of continuing with a NULL pointer or
   a wrapped-around size. */
typedef struct IdAllocHdr { struct IdAllocHdr* prev; struct IdAllocHdr* next; } IdAllocHdr;
static IdAllocHdr* id_arena_head = NULL;
static int id_arena_hooked = 0;
static void id_arena_free_all(void) {
    IdAllocHdr* h = id_arena_head;
    while (h) { IdAllocHdr* nx = h->next; free(h); h = nx; }
    id_arena_head = NULL;
}
static void id_arena_link(IdAllocHdr* h) {
    h->prev = NULL;
    h->next = id_arena_head;
    if (id_arena_head) id_arena_head->prev = h;
    id_arena_head = h;
    if (!id_arena_hooked) { atexit(id_arena_free_all); id_arena_hooked = 1; }
}
static void id_arena_unlink(IdAllocHdr* h) {
    if (h->prev) h->prev->next = h->next; else id_arena_head = h->next;
    if (h->next) h->next->prev = h->prev;
}
static size_t id_add_check(size_t a, size_t b, const char* what) {
    if (a > SIZE_MAX - b) {
        fprintf(stderr, "id: allocation size overflow (%s)\n", what);
        exit(1);
    }
    return a + b;
}
static size_t id_mul_check(size_t a, size_t b, const char* what) {
    if (a != 0 && b > SIZE_MAX / a) {
        fprintf(stderr, "id: allocation size overflow (%s)\n", what);
        exit(1);
    }
    return a * b;
}
static void* id_alloc(size_t n) {
    IdAllocHdr* h = (IdAllocHdr*)malloc(id_add_check(n, sizeof(IdAllocHdr), "alloc"));
    if (!h) { fprintf(stderr, "id: out of memory (%zu bytes)\n", n); exit(1); }
    id_arena_link(h);
    return (void*)(h + 1);
}
static void* id_realloc(void* p, size_t n) {
    if (!p) return id_alloc(n);
    IdAllocHdr* h = (IdAllocHdr*)p - 1;
    id_arena_unlink(h);
    IdAllocHdr* nh = (IdAllocHdr*)realloc(h, id_add_check(n, sizeof(IdAllocHdr), "realloc"));
    if (!nh) { fprintf(stderr, "id: out of memory (%zu bytes)\n", n); exit(1); }
    id_arena_link(nh);
    return (void*)(nh + 1);
}

/* Growable, heap-allocated, reference-semantic list. Every element is stored
   in a uniform 8-byte cell; the compiler boxes/unboxes per the static element
   type. Because a list is a pointer, passing one to a function and mutating it
   is visible to the caller -- this is how id gets shared mutable state.
   Every index access is bounds-checked: an out-of-range get/set/pop is a
   clear, fatal runtime error (never silent corruption or UB), matching id's
   contract that a bug aborts loudly instead of reading/writing garbage. */
typedef struct { int len, cap; long long* data; } IdList;
static IdList* id_list_new(void) {
    IdList* L = (IdList*)id_alloc(sizeof(IdList));
    L->len = 0; L->cap = 4;
    L->data = (long long*)id_alloc(id_mul_check(sizeof(long long), (size_t)L->cap, "list init"));
    return L;
}
static void id_list_push(IdList* L, long long v) {
    if (L->len >= L->cap) {
        if (L->cap > INT_MAX / 2) {
            fprintf(stderr, "id: list capacity overflow\n");
            exit(1);
        }
        int ncap = L->cap * 2;
        L->data = (long long*)id_realloc(L->data,
            id_mul_check(sizeof(long long), (size_t)ncap, "list growth"));
        L->cap = ncap;
    }
    L->data[L->len++] = v;
}
static long long id_list_get(IdList* L, int i) {
    if (i < 0 || i >= L->len) {
        fprintf(stderr, "id: index %d out of bounds (len %d)\n", i, L->len);
        exit(1);
    }
    return L->data[i];
}
static void id_list_set(IdList* L, int i, long long v) {
    if (i < 0 || i >= L->len) {
        fprintf(stderr, "id: index %d out of bounds (len %d)\n", i, L->len);
        exit(1);
    }
    L->data[i] = v;
}
static int id_list_len(IdList* L) { return L->len; }
static long long id_list_pop(IdList* L) {   /* remove & return the last cell */
    if (L->len <= 0) {
        fprintf(stderr, "id: pop from empty list\n");
        exit(1);
    }
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
    size_t n = id_add_check(id_add_check(la, lb, "concat"), 1, "concat");
    char* r = (char*)id_alloc(n);
    memcpy(r, a, la);
    memcpy(r + la, b, lb + 1);
    return r;
}
static char* id_str_of_int(int x) {
    char* r = (char*)id_alloc(32); snprintf(r, 32, "%d", x); return r;
}
static char* id_str_of_float(double x) {
    char* r = (char*)id_alloc(64); snprintf(r, 64, "%g", x); return r;
}
static void id_print(const char* s) { puts(s); }
static char* id_input(void) {
    /* read one line from stdin, drop the trailing newline; "" on EOF */
    char buf[1024];
    if (!fgets(buf, sizeof(buf), stdin)) {
        char* e = (char*)id_alloc(1); e[0] = '\0'; return e;
    }
    size_t n = strlen(buf);
    if (n > 0 && buf[n - 1] == '\n') { buf[--n] = '\0'; }
    char* r = (char*)id_alloc(n + 1); memcpy(r, buf, n + 1); return r;
}
static char* id_read_all(void) {
    /* slurp all of stdin into one string (grows as needed) */
    size_t cap = 4096, n = 0;
    char* r = (char*)id_alloc(cap);
    for (;;) {
        if (n + 1 >= cap) {
            if (cap > SIZE_MAX / 2) {
                fprintf(stderr, "id: allocation size overflow (read_all)\n");
                exit(1);
            }
            cap *= 2;
            r = (char*)id_realloc(r, cap);
        }
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
    char* r = (char*)id_alloc(2);
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
    def __init__(self, funcs_by_file, has_backend=False):
        self.funcs = {}            # name -> FuncDef
        self.exported = {}         # name -> (type, owner fn name)
        self.var_owner = {}        # var name -> (fn name, file, line)
        self.unknown_fns = {}      # name -> (file, line) of first call
        # Whether this build was given --backend: native backends legitimately
        # provide external functions, so a call to an undefined, non-builtin
        # name should only become an `extern` forward declaration (with a
        # warning) when a backend is in play. With no backend, the same call
        # is almost always a typo (e.g. `char_at` for `charat`) and should be
        # a hard error instead of a cryptic linker error later. See
        # gen_expr's call-codegen (the C backend, the only one with an extern
        # mechanism -- LLVM/wasm always reject undefined calls outright).
        self.has_backend = has_backend
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

    def validate(self):
        """Run the checks that don't depend on which backend will emit code
        (function uniqueness, the action/nesting limits). Non-C backends call
        this instead of compile() -- they share this checked AST (self.funcs,
        self.exported, self.var_owner, self.var_types) and the rest of the
        semantic checking (variable resolution, type compatibility) that
        happens inline in each backend's own expression/statement codegen, and
        only diverge from the C backend at codegen itself."""
        self.check_unique_functions()
        for fn in self.funcs.values():
            self.check_action_limit(fn)

    def build_env(self, fn: FuncDef) -> dict:
        """name -> id type for every parameter and every declared local
        (hoisted, function-scoped) in `fn`. Shared by every codegen backend."""
        env = {pname: ptype for ptype, pname in fn.params}
        for stmt in walk_stmts(fn.body):
            if isinstance(stmt, DeclStmt):
                env[stmt.name] = stmt.typ
        return env

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
                               f"and while is one action; return is free) -- move "
                               f"some statements into a helper function to stay "
                               f"within the limit")
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

        # hoist local declarations to function scope: variables are
        # function-scoped (the trailing return clause may reference them)
        env = self.build_env(fn)
        hoisted = [f"    {self.c_decl(stmt.typ, stmt.name)};"
                   for stmt in walk_stmts(fn.body)
                   if isinstance(stmt, DeclStmt) and not stmt.exported]
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
            if not self.has_backend:
                # No --backend means there is nowhere this name could be
                # resolved from at link time, so it's almost certainly a
                # typo'd builtin or a forgotten function -- fail now with a
                # helpful message instead of an `extern` that turns into a
                # bare linker error.
                raise CompileError(e.file, e.line, no_such_function_msg(e.name))
            if e.name not in self.unknown_fns:
                hint = builtin_hint(e.name)
                warn(e.file, e.line,
                     f"call to function '{e.name}' which is not defined in any input "
                     f"file; it must be provided at link time"
                     + (f".{hint}" if hint else ""))
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


# ---------------------------------------------------------------- LLVM backend
#
# Emits textual LLVM IR for the *user* id functions only; the runtime (list,
# string, and I/O primitives) stays the existing C `RUNTIME` string, compiled
# and linked in by clang alongside the generated .ll. Every id value is either
# an i32 (int), a double (float), or an opaque `ptr` (string, or any list type
# -- lists are always the generic IdList* the runtime already implements, so
# no struct layout needs to be replicated here). Every mutable id variable
# (parameter or local) gets an `alloca` in the function's entry block and is
# read/written via plain load/store -- the same "no SSA/no phi" style clang
# itself emits at -O0, so no phi-node bookkeeping is needed for if/while.
# Real-time I/O and graphics builtins (put/flush/getkey/sleep_ms/ticks) and
# calls to functions not defined anywhere in the program are out of scope for
# this backend and are rejected with a clear error.

def ll_type(typ):
    if typ == "int":
        return "i32"
    if typ == "float":
        return "double"
    if typ == "void":
        return "void"
    return "ptr"   # string, or any list type


def unescape_id_string(raw: str) -> bytes:
    """The lexer accepts `\\.` (backslash + any char) inside a string literal
    and the C backend just copies `raw` verbatim into C source, relying on the
    C compiler to interpret the escapes. Backends that don't hand the literal
    to a C compiler must interpret them themselves; this covers the common
    escapes and otherwise keeps the escaped character literally."""
    assert raw[0] == '"' and raw[-1] == '"'
    s = raw[1:-1]
    out = bytearray()
    i = 0
    mapping = {"n": 10, "t": 9, "r": 13, "\\": 92, '"': 34, "0": 0}
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            out.append(mapping.get(s[i + 1], ord(s[i + 1])))
            i += 2
        else:
            out.extend(c.encode("utf-8"))
            i += 1
    return bytes(out)


def ll_string_const(bs: bytes):
    """A `c"..."` LLVM string-array literal (with a trailing NUL) for raw bytes
    `bs`, and its byte length (including the NUL)."""
    parts = []
    for b in bs:
        c = chr(b)
        if 32 <= b < 127 and c not in ('"', "\\"):
            parts.append(c)
        else:
            parts.append("\\%02X" % b)
    parts.append("\\00")
    return 'c"' + "".join(parts) + '"', len(bs) + 1


LLVM_RUNTIME_DECLARES = """\
declare ptr @id_list_new()
declare void @id_list_push(ptr, i64)
declare i64 @id_list_get(ptr, i32)
declare void @id_list_set(ptr, i32, i64)
declare i32 @id_list_len(ptr)
declare i64 @id_list_pop(ptr)
declare i64 @id_box_f(double)
declare double @id_unbox_f(i64)
declare i32 @id_to_int(ptr)
declare ptr @id_concat(ptr, ptr)
declare ptr @id_str_of_int(i32)
declare ptr @id_str_of_float(double)
declare void @id_print(ptr)
declare ptr @id_input()
declare ptr @id_read_all()
declare i32 @id_len(ptr)
declare i32 @id_charat(ptr, i32)
declare ptr @id_chr(i32)
declare i32 @strcmp(ptr, ptr)
"""

UNSUPPORTED_BUILTINS = ("put", "flush", "getkey", "sleep_ms", "ticks")


class LLVMBackend:
    """Emits one LLVM IR module (as text) for a checked program. Shares the
    Compiler's checked tables (funcs/exported/var_owner) and re-derives typing
    the same way Compiler.gen_expr does, just producing IR instructions
    instead of C code; the remaining semantic checks (variable resolution,
    type compatibility) that Compiler's own codegen performs inline are
    therefore performed here too, via the same helper methods."""

    def __init__(self, compiler: Compiler):
        self.compiler = compiler
        self.str_table = {}   # bytes -> "@.strN"

    # -- string constants (module-wide, discovered while emitting bodies)

    def str_const(self, raw: str) -> str:
        bs = unescape_id_string(raw)
        name = self.str_table.get(bs)
        if name is None:
            name = f"@.str{len(self.str_table)}"
            self.str_table[bs] = name
        return name

    # -- per-function state

    def new_tmp(self) -> str:
        self.tmp_n += 1
        return f"%t{self.tmp_n}"

    def new_lbl_id(self) -> int:
        self.lbl_n += 1
        return self.lbl_n

    def emit(self, line: str):
        self.lines.append(line)

    def read_var(self, name, typ):
        t = self.new_tmp()
        if name in self.compiler.exported:
            self.emit(f"  {t} = load {ll_type(typ)}, ptr @g_{name}")
        else:
            self.emit(f"  {t} = load {ll_type(typ)}, ptr %v_{name}")
        return t

    def write_var(self, name, val, typ):
        if name in self.compiler.exported:
            self.emit(f"  store {ll_type(typ)} {val}, ptr @g_{name}")
        else:
            self.emit(f"  store {ll_type(typ)} {val}, ptr %v_{name}")

    def coerce(self, val, have, want):
        if have == want:
            return val
        if have == "int" and want == "float":
            t = self.new_tmp()
            self.emit(f"  {t} = sitofp i32 {val} to double")
            return t
        return val

    def box(self, val, typ):
        if typ == "int":
            t = self.new_tmp()
            self.emit(f"  {t} = sext i32 {val} to i64")
            return t
        if typ == "float":
            t = self.new_tmp()
            self.emit(f"  {t} = call i64 @id_box_f(double {val})")
            return t
        t = self.new_tmp()
        self.emit(f"  {t} = ptrtoint ptr {val} to i64")
        return t

    def unbox(self, val, typ):
        if typ == "int":
            t = self.new_tmp()
            self.emit(f"  {t} = trunc i64 {val} to i32")
            return t
        if typ == "float":
            t = self.new_tmp()
            self.emit(f"  {t} = call double @id_unbox_f(i64 {val})")
            return t
        t = self.new_tmp()
        self.emit(f"  {t} = inttoptr i64 {val} to ptr")
        return t

    def to_i1(self, val, typ):
        t = self.new_tmp()
        if typ == "float":
            self.emit(f"  {t} = fcmp one double {val}, 0.0")
        elif typ == "int":
            self.emit(f"  {t} = icmp ne i32 {val}, 0")
        else:
            self.emit(f"  {t} = icmp ne ptr {val}, null")
        return t

    def to_string(self, val, typ, e):
        if typ == "string":
            return val
        if typ == "int":
            t = self.new_tmp()
            self.emit(f"  {t} = call ptr @id_str_of_int(i32 {val})")
            return t
        if typ == "float":
            t = self.new_tmp()
            self.emit(f"  {t} = call ptr @id_str_of_float(double {val})")
            return t
        raise CompileError(e.file, e.line, f"cannot convert {typ} to string")

    # -- function codegen

    def gen_function(self, fn: FuncDef) -> str:
        self.env = self.compiler.build_env(fn)
        self.lines = []
        self.tmp_n = 0
        self.lbl_n = 0
        params_sig = ", ".join(f"{ll_type(t)} %arg_{n}" for t, n in fn.params)
        header = f"define {ll_type(fn.rettype)} @id_{fn.name}({params_sig}) {{"
        self.emit("entry:")
        for name, typ in self.env.items():
            if name in self.compiler.exported:
                continue
            self.emit(f"  %v_{name} = alloca {ll_type(typ)}")
        for ptype, pname in fn.params:
            self.emit(f"  store {ll_type(ptype)} %arg_{pname}, ptr %v_{pname}")
        for stmt in fn.body:
            self.gen_stmt(stmt, fn)
        if fn.rettype == "void":
            self.emit("  ret void")
        else:
            val, typ = self.gen_expr(fn.retexpr, fn, fn.rettype)
            if not compatible(fn.rettype, typ):
                raise CompileError(fn.retexpr.file, fn.retexpr.line,
                                   f"function '{fn.name}' returns {fn.rettype} but "
                                   f"the expression has type {typ}")
            val = self.coerce(val, typ, fn.rettype)
            self.emit(f"  ret {ll_type(fn.rettype)} {val}")
        return header + "\n" + "\n".join(self.lines) + "\n}\n"

    def gen_stmt(self, stmt, fn):
        if isinstance(stmt, DeclStmt):
            val, typ = self.gen_expr(stmt.expr, fn, stmt.typ)
            if not compatible(stmt.typ, typ):
                raise CompileError(stmt.file, stmt.line,
                                   f"cannot initialize {stmt.typ} '{stmt.name}' "
                                   f"with a {typ} value")
            val = self.coerce(val, typ, stmt.typ)
            self.write_var(stmt.name, val, stmt.typ)
            return
        if isinstance(stmt, AssignStmt):
            if stmt.name not in self.env:
                self.compiler.explain_bad_var(stmt.name, fn, stmt.file, stmt.line)
            want = self.env[stmt.name]
            val, typ = self.gen_expr(stmt.expr, fn, want)
            if not compatible(want, typ):
                raise CompileError(stmt.file, stmt.line,
                                   f"cannot assign a {typ} value to {want} "
                                   f"'{stmt.name}'")
            val = self.coerce(val, typ, want)
            self.write_var(stmt.name, val, want)
            return
        if isinstance(stmt, IndexAssignStmt):
            base, btyp = self.gen_expr(stmt.base, fn)
            if not btyp.endswith("[]"):
                raise CompileError(stmt.file, stmt.line, f"cannot index a {btyp}")
            idx, ityp = self.gen_expr(stmt.index, fn)
            if ityp != "int":
                raise CompileError(stmt.file, stmt.line,
                                   f"list index must be int, got {ityp}")
            elem = btyp[:-2]
            val, typ = self.gen_expr(stmt.expr, fn, elem)
            if not compatible(elem, typ):
                raise CompileError(stmt.file, stmt.line,
                                   f"cannot store a {typ} into a {btyp}")
            val = self.coerce(val, typ, elem)
            boxed = self.box(val, elem)
            self.emit(f"  call void @id_list_set(ptr {base}, i32 {idx}, i64 {boxed})")
            return
        if isinstance(stmt, IfStmt):
            end_l = f"if.end{self.new_lbl_id()}"
            self.gen_if_chain(stmt, fn, end_l)
            self.emit(f"{end_l}:")
            return
        if isinstance(stmt, WhileStmt):
            n = self.new_lbl_id()
            cond_l, body_l, end_l = f"while.cond{n}", f"while.body{n}", f"while.end{n}"
            self.emit(f"  br label %{cond_l}")
            self.emit(f"{cond_l}:")
            cond, ctyp = self.gen_expr(stmt.cond, fn)
            if ctyp == "void":
                raise CompileError(stmt.file, stmt.line, "loop condition has type void")
            i1 = self.to_i1(cond, ctyp)
            self.emit(f"  br i1 {i1}, label %{body_l}, label %{end_l}")
            self.emit(f"{body_l}:")
            for s in stmt.body:
                self.gen_stmt(s, fn)
            self.emit(f"  br label %{cond_l}")
            self.emit(f"{end_l}:")
            return
        if isinstance(stmt, ExprStmt):
            self.gen_expr(stmt.expr, fn)
            return
        raise AssertionError(stmt)

    def gen_if_chain(self, stmt: IfStmt, fn, end_label):
        n = self.new_lbl_id()
        then_l = f"if.then{n}"
        cond, ctyp = self.gen_expr(stmt.cond, fn)
        if ctyp == "void":
            raise CompileError(stmt.file, stmt.line, "condition has type void")
        i1 = self.to_i1(cond, ctyp)
        if stmt.els is None:
            else_l = end_label
        else:
            else_l = f"if.else{n}"
        self.emit(f"  br i1 {i1}, label %{then_l}, label %{else_l}")
        self.emit(f"{then_l}:")
        for s in stmt.then:
            self.gen_stmt(s, fn)
        self.emit(f"  br label %{end_label}")
        if stmt.els is None:
            return
        self.emit(f"{else_l}:")
        if isinstance(stmt.els, IfStmt):
            self.gen_if_chain(stmt.els, fn, end_label)
        else:
            for s in stmt.els:
                self.gen_stmt(s, fn)
            self.emit(f"  br label %{end_label}")

    # -- expressions: returns (ir_value, id_type)

    def gen_expr(self, e, fn, expected=None):
        if isinstance(e, IntLit):
            return e.value, "int"
        if isinstance(e, FloatLit):
            return e.value, "float"
        if isinstance(e, StrLit):
            return self.str_const(e.raw), "string"
        if isinstance(e, VarRef):
            if e.name not in self.env:
                self.compiler.explain_bad_var(e.name, fn, e.file, e.line)
            typ = self.env[e.name]
            return self.read_var(e.name, typ), typ
        if isinstance(e, ImportRef):
            if e.name not in self.compiler.exported:
                if e.name in self.compiler.var_owner:
                    owner = self.compiler.var_owner[e.name][0]
                    raise CompileError(e.file, e.line,
                                       f"variable '{e.name}' (in function '{owner}') "
                                       f"is not exported")
                raise CompileError(e.file, e.line,
                                   f"no exported variable named '{e.name}'")
            typ = self.compiler.exported[e.name][0]
            return self.read_var(e.name, typ), typ
        if isinstance(e, IndexExpr):
            base, btyp = self.gen_expr(e.base, fn)
            if not btyp.endswith("[]"):
                raise CompileError(e.file, e.line, f"cannot index a {btyp}")
            idx, ityp = self.gen_expr(e.index, fn)
            if ityp != "int":
                raise CompileError(e.file, e.line, f"array index must be int, got {ityp}")
            elem = btyp[:-2]
            t = self.new_tmp()
            self.emit(f"  {t} = call i64 @id_list_get(ptr {base}, i32 {idx})")
            return self.unbox(t, elem), elem
        if isinstance(e, ArrayLit):
            if not e.elems:
                if expected is None or not expected.endswith("[]"):
                    raise CompileError(e.file, e.line,
                                       "an empty list literal needs a known list "
                                       "type here (e.g. on a typed declaration)")
                t = self.new_tmp()
                self.emit(f"  {t} = call ptr @id_list_new()")
                return t, expected
            raw, etyp = [], None
            for el in e.elems:
                val, typ = self.gen_expr(el, fn)
                if etyp is None:
                    etyp = typ
                elif not compatible(etyp, typ):
                    raise CompileError(el.file, el.line,
                                       f"list element has type {typ}, expected {etyp}")
                if is_numeric(etyp) and typ == "float":
                    etyp = "float"
                raw.append((val, typ))
            t = self.new_tmp()
            self.emit(f"  {t} = call ptr @id_list_new()")
            for val, typ in raw:
                val = self.coerce(val, typ, etyp)
                boxed = self.box(val, etyp)
                self.emit(f"  call void @id_list_push(ptr {t}, i64 {boxed})")
            return t, etyp + "[]"
        if isinstance(e, CallExpr):
            return self.gen_call(e, fn)
        if isinstance(e, UnOp):
            val, typ = self.gen_expr(e.operand, fn)
            if e.op == "-":
                if not is_numeric(typ):
                    raise CompileError(e.file, e.line, f"cannot negate a {typ}")
                t = self.new_tmp()
                if typ == "int":
                    self.emit(f"  {t} = sub i32 0, {val}")
                else:
                    self.emit(f"  {t} = fneg double {val}")
                return t, typ
            if e.op == "!":
                if typ != "int":
                    raise CompileError(e.file, e.line, f"cannot apply '!' to a {typ}")
                t1 = self.new_tmp()
                self.emit(f"  {t1} = icmp eq i32 {val}, 0")
                t2 = self.new_tmp()
                self.emit(f"  {t2} = zext i1 {t1} to i32")
                return t2, "int"
            raise AssertionError(e.op)
        if isinstance(e, BinOp):
            return self.gen_binop(e, fn)
        raise AssertionError(e)

    def gen_binop(self, e: BinOp, fn):
        lc, lt = self.gen_expr(e.left, fn)
        rc, rt = self.gen_expr(e.right, fn)
        op = e.op
        if op == "+" and (lt == "string" or rt == "string"):
            ls = self.to_string(lc, lt, e.left)
            rs = self.to_string(rc, rt, e.right)
            t = self.new_tmp()
            self.emit(f"  {t} = call ptr @id_concat(ptr {ls}, ptr {rs})")
            return t, "string"
        if op in ("==", "!="):
            if lt == "string" and rt == "string":
                t1 = self.new_tmp()
                self.emit(f"  {t1} = call i32 @strcmp(ptr {lc}, ptr {rc})")
                cmp = "eq" if op == "==" else "ne"
                t2 = self.new_tmp()
                self.emit(f"  {t2} = icmp {cmp} i32 {t1}, 0")
                t3 = self.new_tmp()
                self.emit(f"  {t3} = zext i1 {t2} to i32")
                return t3, "int"
            if is_numeric(lt) and is_numeric(rt):
                common = "float" if "float" in (lt, rt) else "int"
                lc2 = self.coerce(lc, lt, common)
                rc2 = self.coerce(rc, rt, common)
                t1 = self.new_tmp()
                if common == "int":
                    cmp = "eq" if op == "==" else "ne"
                    self.emit(f"  {t1} = icmp {cmp} i32 {lc2}, {rc2}")
                else:
                    cmp = "oeq" if op == "==" else "one"
                    self.emit(f"  {t1} = fcmp {cmp} double {lc2}, {rc2}")
                t2 = self.new_tmp()
                self.emit(f"  {t2} = zext i1 {t1} to i32")
                return t2, "int"
            raise CompileError(e.file, e.line, f"cannot compare {lt} with {rt}")
        if op in ("<", "<=", ">", ">="):
            if is_numeric(lt) and is_numeric(rt):
                common = "float" if "float" in (lt, rt) else "int"
                lc2 = self.coerce(lc, lt, common)
                rc2 = self.coerce(rc, rt, common)
                imap = {"<": "slt", "<=": "sle", ">": "sgt", ">=": "sge"}
                fmap = {"<": "olt", "<=": "ole", ">": "ogt", ">=": "oge"}
                t1 = self.new_tmp()
                if common == "int":
                    self.emit(f"  {t1} = icmp {imap[op]} i32 {lc2}, {rc2}")
                else:
                    self.emit(f"  {t1} = fcmp {fmap[op]} double {lc2}, {rc2}")
                t2 = self.new_tmp()
                self.emit(f"  {t2} = zext i1 {t1} to i32")
                return t2, "int"
            raise CompileError(e.file, e.line, f"cannot order {lt} and {rt}")
        if op in ("&&", "||"):
            if lt == "int" and rt == "int":
                lb = self.new_tmp()
                self.emit(f"  {lb} = icmp ne i32 {lc}, 0")
                rb = self.new_tmp()
                self.emit(f"  {rb} = icmp ne i32 {rc}, 0")
                t1 = self.new_tmp()
                instr = "and" if op == "&&" else "or"
                self.emit(f"  {t1} = {instr} i1 {lb}, {rb}")
                t2 = self.new_tmp()
                self.emit(f"  {t2} = zext i1 {t1} to i32")
                return t2, "int"
            raise CompileError(e.file, e.line, f"'{op}' requires int operands")
        if op in ("+", "-", "*", "/", "%"):
            if is_numeric(lt) and is_numeric(rt):
                if op == "%" and (lt == "float" or rt == "float"):
                    raise CompileError(e.file, e.line, "'%' requires int operands")
                res = "float" if "float" in (lt, rt) else "int"
                lc2 = self.coerce(lc, lt, res)
                rc2 = self.coerce(rc, rt, res)
                t = self.new_tmp()
                if res == "int":
                    instr = {"+": "add", "-": "sub", "*": "mul",
                             "/": "sdiv", "%": "srem"}[op]
                    self.emit(f"  {t} = {instr} i32 {lc2}, {rc2}")
                else:
                    instr = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv"}[op]
                    self.emit(f"  {t} = {instr} double {lc2}, {rc2}")
                return t, res
            raise CompileError(e.file, e.line, f"cannot apply '{op}' to {lt} and {rt}")
        raise AssertionError(op)

    def gen_call(self, e: CallExpr, fn):
        name = e.name
        if name == "print":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "print takes exactly one argument")
            val, typ = self.gen_expr(e.args[0], fn)
            s = self.to_string(val, typ, e)
            self.emit(f"  call void @id_print(ptr {s})")
            return "0", "void"
        if name == "input":
            if e.args:
                raise CompileError(e.file, e.line, "input takes no arguments")
            t = self.new_tmp()
            self.emit(f"  {t} = call ptr @id_input()")
            return t, "string"
        if name == "read_all":
            if e.args:
                raise CompileError(e.file, e.line, "read_all takes no arguments")
            t = self.new_tmp()
            self.emit(f"  {t} = call ptr @id_read_all()")
            return t, "string"
        if name == "len":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "len takes exactly one argument")
            val, typ = self.gen_expr(e.args[0], fn)
            t = self.new_tmp()
            if typ == "string":
                self.emit(f"  {t} = call i32 @id_len(ptr {val})")
            elif typ.endswith("[]"):
                self.emit(f"  {t} = call i32 @id_list_len(ptr {val})")
            else:
                raise CompileError(e.file, e.line,
                                   f"len expects a string or list, got {typ}")
            return t, "int"
        if name == "push":
            if len(e.args) != 2:
                raise CompileError(e.file, e.line, "push takes exactly two arguments")
            lc, lt = self.gen_expr(e.args[0], fn)
            if not lt.endswith("[]"):
                raise CompileError(e.file, e.line, f"push expects a list, got {lt}")
            elem = lt[:-2]
            vc, vt = self.gen_expr(e.args[1], fn, elem)
            if not compatible(elem, vt):
                raise CompileError(e.file, e.line, f"cannot push a {vt} onto a {lt}")
            vc = self.coerce(vc, vt, elem)
            boxed = self.box(vc, elem)
            self.emit(f"  call void @id_list_push(ptr {lc}, i64 {boxed})")
            return "0", "void"
        if name == "pop":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "pop takes exactly one argument")
            lc, lt = self.gen_expr(e.args[0], fn)
            if not lt.endswith("[]"):
                raise CompileError(e.file, e.line, f"pop expects a list, got {lt}")
            elem = lt[:-2]
            t = self.new_tmp()
            self.emit(f"  {t} = call i64 @id_list_pop(ptr {lc})")
            return self.unbox(t, elem), elem
        if name == "to_int":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "to_int takes exactly one argument")
            val, typ = self.gen_expr(e.args[0], fn)
            if typ != "string":
                raise CompileError(e.file, e.line, f"to_int expects a string, got {typ}")
            t = self.new_tmp()
            self.emit(f"  {t} = call i32 @id_to_int(ptr {val})")
            return t, "int"
        if name == "charat":
            if len(e.args) != 2:
                raise CompileError(e.file, e.line, "charat takes exactly two arguments")
            sc, st = self.gen_expr(e.args[0], fn)
            ic, it = self.gen_expr(e.args[1], fn)
            if st != "string":
                raise CompileError(e.file, e.line, f"charat expects a string, got {st}")
            if it != "int":
                raise CompileError(e.file, e.line, f"charat index must be int, got {it}")
            t = self.new_tmp()
            self.emit(f"  {t} = call i32 @id_charat(ptr {sc}, i32 {ic})")
            return t, "int"
        if name == "chr":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "chr takes exactly one argument")
            val, typ = self.gen_expr(e.args[0], fn)
            if typ != "int":
                raise CompileError(e.file, e.line, f"chr expects an int, got {typ}")
            t = self.new_tmp()
            self.emit(f"  {t} = call ptr @id_chr(i32 {val})")
            return t, "string"
        if name in UNSUPPORTED_BUILTINS:
            raise CompileError(e.file, e.line,
                               f"builtin '{name}' is not supported for this "
                               f"--target (real-time I/O is C-only)")
        args = [self.gen_expr(a, fn) for a in e.args]
        callee = self.compiler.funcs.get(name)
        if callee is None:
            raise CompileError(e.file, e.line,
                               f"call to external function '{name}' is not "
                               f"supported for this --target (only functions "
                               f"defined in the program are supported)."
                               f"{builtin_hint(name)}")
        if len(args) != len(callee.params):
            raise CompileError(e.file, e.line,
                               f"function '{name}' takes {len(callee.params)} "
                               f"argument(s), got {len(args)}")
        argstrs = []
        for (ptype, pname), (val, typ), arg in zip(callee.params, args, e.args):
            if not compatible(ptype, typ):
                raise CompileError(arg.file, arg.line,
                                   f"argument '{pname}' of '{name}' expects "
                                   f"{ptype}, got {typ}")
            val = self.coerce(val, typ, ptype)
            argstrs.append(f"{ll_type(ptype)} {val}")
        if callee.rettype == "void":
            self.emit(f"  call void @id_{name}({', '.join(argstrs)})")
            return "0", "void"
        t = self.new_tmp()
        self.emit(f"  {t} = call {ll_type(callee.rettype)} @id_{name}({', '.join(argstrs)})")
        return t, callee.rettype

    # -- C-ABI entrypoint (marshals argv into an id string[] the same way the
    #    C backend's gen_entrypoint does, then calls id_main)

    def gen_entrypoint(self) -> str:
        m = self.compiler.funcs.get("main")
        if m is None:
            return ""
        ptypes = [t for t, _ in m.params]
        lines = ["define i32 @main(i32 %argc, ptr %argv) {", "entry:"]
        if ptypes == ["int", "string[]"]:
            lines += [
                "  %args = call ptr @id_list_new()",
                "  %i.addr = alloca i32",
                "  store i32 0, ptr %i.addr",
                "  br label %loop.cond",
                "loop.cond:",
                "  %i.val = load i32, ptr %i.addr",
                "  %cmp = icmp slt i32 %i.val, %argc",
                "  br i1 %cmp, label %loop.body, label %loop.end",
                "loop.body:",
                "  %idx64 = sext i32 %i.val to i64",
                "  %elemptr = getelementptr ptr, ptr %argv, i64 %idx64",
                "  %s = load ptr, ptr %elemptr",
                "  %sbox = ptrtoint ptr %s to i64",
                "  call void @id_list_push(ptr %args, i64 %sbox)",
                "  %i.next = add i32 %i.val, 1",
                "  store i32 %i.next, ptr %i.addr",
                "  br label %loop.cond",
                "loop.end:",
            ]
            call = "@id_main(i32 %argc, ptr %args)"
        elif ptypes == []:
            call = "@id_main()"
        else:
            raise CompileError(m.file, m.line,
                               "main must take (int, string[]) or no parameters")
        if m.rettype == "int":
            lines.append(f"  %r = call i32 {call}")
            lines.append("  ret i32 %r")
        else:
            lines.append(f"  call void {call}")
            lines.append("  ret i32 0")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def emit_module(self) -> str:
        func_bodies = [self.gen_function(fn) for fn in self.compiler.funcs.values()]

        out = ['target triple = "x86_64-unknown-linux-gnu"', ""]
        out.append(LLVM_RUNTIME_DECLARES)

        if self.compiler.exported:
            out.append("; exported variables")
            for name, (typ, owner) in self.compiler.exported.items():
                zero = {"int": "0", "float": "0.0"}.get(typ, "null")
                out.append(f"@g_{name} = global {ll_type(typ)} {zero}  ; exported by {owner}()")
            out.append("")

        if self.str_table:
            out.append("; string constants")
            for bs, name in self.str_table.items():
                content, size = ll_string_const(bs)
                out.append(f"{name} = private unnamed_addr constant [{size} x i8] {content}")
            out.append("")

        out.extend(func_bodies)
        out.append(self.gen_entrypoint())
        return "\n".join(out) + "\n"


# ---------------------------------------------------------------- WASM backend
#
# Emits a self-contained WebAssembly module as WAT text, assembled with
# wat2wasm and run as a WASI "command" module under wasmtime. Unlike the LLVM
# backend, this does NOT reuse the C `RUNTIME` -- linking real libc into
# wasm32 needs a wasi-sysroot, which isn't available in this environment (only
# llvm/clang/lld/wabt/wasmtime are provided, no wasi-sysroot), so every runtime
# primitive (the growable list, string ops, and I/O) is hand-written here in
# WAT, using a single linear memory with a bump allocator (nothing is ever
# freed -- the same lifetime model the C RUNTIME already uses) and the
# `wasi_snapshot_preview1` imports directly (fd_write/fd_read/args_*/proc_exit)
# instead of libc. An id value is represented as: int -> i32, float -> f64,
# string / any list type -> i32 (an address in linear memory: a NUL-terminated
# byte string, or a 12-byte IdList header [len:i32][cap:i32][data-ptr:i32]).
# List cells are i64 (matching the C runtime's `long long` cells).
#
# WAT's structured `if`/`loop` line up with id's if/while directly, so (unlike
# the LLVM backend) no manual basic-block/label plumbing is needed for control
# flow; expressions are emitted as folded (fully nested) s-expressions, mirroring
# the C backend's approach of returning a single self-contained code string per
# expression.
#
# Real-time I/O/graphics builtins and calls to functions not defined anywhere
# in the program are out of scope (same as the LLVM backend). Converting a
# float to a string (print/concat) is also not implemented for this target.

# fixed low-memory scratch addresses (never touched by the bump allocator)
_IOV0_PTR, _IOV0_LEN, _IOV1_PTR, _IOV1_LEN = 0, 4, 8, 12
_NWRITTEN = 16
_NEWLINE_BYTE = 20
_ARGC_SCRATCH, _BUFSIZE_SCRATCH = 24, 28
_READ_IOV_PTR, _READ_IOV_LEN, _READ_NREAD, _READ_BYTE = 32, 36, 40, 44
_STROI_BUF = 64        # 32 bytes, for id_str_of_int's digit scratch
_INPUT_BUF = 128       # 1024 bytes, input()'s line buffer

# fixed fatal-error message bytes (mirroring the C RUNTIME's stderr messages)
# for the wasm target's own bounds/allocation traps -- laid out in the same
# never-touched-by-the-bump-allocator region as the scratch addresses above.
_MSG_IDX_PRE = b"id: index "
_MSG_IDX_MID = b" out of bounds (len "
_MSG_IDX_END = b")\n"
_MSG_POP = b"id: pop from empty list\n"
_MSG_OOM = b"id: out of memory\n"
_MSG_CAP = b"id: list capacity overflow\n"

_MSG_IDX_PRE_ADDR = 1152
_MSG_IDX_MID_ADDR = _MSG_IDX_PRE_ADDR + len(_MSG_IDX_PRE)
_MSG_IDX_END_ADDR = _MSG_IDX_MID_ADDR + len(_MSG_IDX_MID)
_MSG_POP_ADDR = _MSG_IDX_END_ADDR + len(_MSG_IDX_END)
_MSG_OOM_ADDR = _MSG_POP_ADDR + len(_MSG_POP)
_MSG_CAP_ADDR = _MSG_OOM_ADDR + len(_MSG_OOM)

_RESERVED_END = 2048   # string constants (and then the heap) start here
assert _MSG_CAP_ADDR + len(_MSG_CAP) <= _RESERVED_END


def wat_bytes_literal(bs: bytes) -> str:
    """A WAT `(data ...)` string literal for raw bytes `bs`, NUL-terminated."""
    out = []
    for b in bs:
        c = chr(b)
        if b == 0x22:
            out.append('\\22')
        elif b == 0x5c:
            out.append('\\5c')
        elif 32 <= b < 127:
            out.append(c)
        else:
            out.append("\\%02x" % b)
    out.append("\\00")
    return "".join(out)


def wasm_runtime_funcs() -> str:
    return f"""\
  ;; ---- fatal errors: write a message to stderr (fd 2) and exit(1). Unlike a
  ;; bare `unreachable` (which the wasm engine reports as an opaque trap),
  ;; this gives the same clear "id: ..." message and exit code the C target
  ;; produces for the same conditions. The `unreachable` after `proc_exit`
  ;; is dead in practice (proc_exit terminates the instance) but keeps every
  ;; branch that calls these well-typed regardless of its result type.
  (func $id_write_all (param $fd i32) (param $ptr i32) (param $len i32)
    ;; fd_write (like POSIX writev) may perform a short write -- it can write
    ;; fewer bytes than asked and still return success, leaving the rest for a
    ;; follow-up call. Loop, advancing by whatever it actually wrote, until
    ;; every byte is out (or it stops making progress, e.g. on a real error).
    (local $got i32)
    (block $done
      (loop $again
        (br_if $done (i32.le_s (local.get $len) (i32.const 0)))
        (i32.store (i32.const {_IOV0_PTR}) (local.get $ptr))
        (i32.store (i32.const {_IOV0_LEN}) (local.get $len))
        (drop (call $fd_write (local.get $fd) (i32.const {_IOV0_PTR}) (i32.const 1)
                               (i32.const {_NWRITTEN})))
        (local.set $got (i32.load (i32.const {_NWRITTEN})))
        (br_if $done (i32.le_s (local.get $got) (i32.const 0)))
        (local.set $ptr (i32.add (local.get $ptr) (local.get $got)))
        (local.set $len (i32.sub (local.get $len) (local.get $got)))
        (br $again))))

  (func $id_die (param $ptr i32) (param $len i32)
    (call $id_write_all (i32.const 2) (local.get $ptr) (local.get $len))
    (call $proc_exit (i32.const 1))
    (unreachable))

  (func $id_index_error (param $idx i32) (param $len i32)
    (local $s i32)
    (call $id_write_all (i32.const 2) (i32.const {_MSG_IDX_PRE_ADDR})
                         (i32.const {len(_MSG_IDX_PRE)}))
    (local.set $s (call $id_str_of_int (local.get $idx)))
    (call $id_write_all (i32.const 2) (local.get $s) (call $id_strlen (local.get $s)))
    (call $id_write_all (i32.const 2) (i32.const {_MSG_IDX_MID_ADDR})
                         (i32.const {len(_MSG_IDX_MID)}))
    (local.set $s (call $id_str_of_int (local.get $len)))
    (call $id_write_all (i32.const 2) (local.get $s) (call $id_strlen (local.get $s)))
    (call $id_write_all (i32.const 2) (i32.const {_MSG_IDX_END_ADDR})
                         (i32.const {len(_MSG_IDX_END)}))
    (call $proc_exit (i32.const 1))
    (unreachable))

  (func $id_pop_error
    (call $id_die (i32.const {_MSG_POP_ADDR}) (i32.const {len(_MSG_POP)})))

  (func $id_oom_error
    (call $id_die (i32.const {_MSG_OOM_ADDR}) (i32.const {len(_MSG_OOM)})))

  (func $id_cap_overflow_error
    (call $id_die (i32.const {_MSG_CAP_ADDR}) (i32.const {len(_MSG_CAP)})))

  ;; Bump allocator over the wasm linear memory. Unlike the C target's
  ;; malloc/realloc, wasm memory can only grow (never shrink/free), but a
  ;; naive bump that never grows the memory would let later loads/stores walk
  ;; off the end of the allocated pages -- which the engine catches as an
  ;; opaque trap, but only *after* silently handing out a pointer into
  ;; unmapped space. Instead, check up front whether the requested block
  ;; still fits in the currently-allocated pages and, if not, grow memory to
  ;; cover it -- growth failure (address space exhausted) is reported the
  ;; same way as a C-side OOM.
  (func $id_alloc (param $n i32) (result i32)
    (local $p i32) (local $need i32) (local $have i32) (local $want i32) (local $grown i32)
    (local.set $p (global.get $heap))
    (local.set $need (i32.add (local.get $p) (local.get $n)))
    (local.set $have (i32.mul (memory.size) (i32.const 65536)))
    (if (i32.gt_u (local.get $need) (local.get $have))
      (then
        (local.set $want
          (i32.div_u (i32.add (i32.sub (local.get $need) (local.get $have)) (i32.const 65535))
                     (i32.const 65536)))
        (local.set $grown (memory.grow (local.get $want)))
        (if (i32.eq (local.get $grown) (i32.const -1))
          (then (call $id_oom_error) (unreachable)))))
    (global.set $heap (local.get $need))
    (local.get $p))

  (func $id_memcopy (param $dst i32) (param $src i32) (param $n i32)
    (local $i i32)
    (local.set $i (i32.const 0))
    (block $done
      (loop $again
        (br_if $done (i32.ge_u (local.get $i) (local.get $n)))
        (i32.store8 (i32.add (local.get $dst) (local.get $i))
                    (i32.load8_u (i32.add (local.get $src) (local.get $i))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $again))))

  (func $id_list_new (result i32)
    (local $L i32)
    (local.set $L (call $id_alloc (i32.const 12)))
    (i32.store (local.get $L) (i32.const 0))
    (i32.store offset=4 (local.get $L) (i32.const 4))
    (i32.store offset=8 (local.get $L) (call $id_alloc (i32.const 32)))
    (local.get $L))

  (func $id_list_grow (param $L i32)
    (local $cap i32) (local $data i32) (local $ndata i32) (local $ncap i32)
    (local.set $cap (i32.load offset=4 (local.get $L)))
    (local.set $data (i32.load offset=8 (local.get $L)))
    ;; guard the same integer-overflow-in-sizing that the C runtime guards:
    ;; below this cap, `cap * 2` and `(cap * 2) * 8` both stay well under
    ;; 2^32, so neither the capacity doubling nor the byte-size computation
    ;; can wrap around.
    (if (i32.ge_u (local.get $cap) (i32.const 134217728))
      (then (call $id_cap_overflow_error) (unreachable)))
    (local.set $ncap (i32.mul (local.get $cap) (i32.const 2)))
    (local.set $ndata (call $id_alloc (i32.mul (local.get $ncap) (i32.const 8))))
    (call $id_memcopy (local.get $ndata) (local.get $data)
                       (i32.mul (local.get $cap) (i32.const 8)))
    (i32.store offset=8 (local.get $L) (local.get $ndata))
    (i32.store offset=4 (local.get $L) (local.get $ncap)))

  (func $id_list_push (param $L i32) (param $v i64)
    (local $len i32) (local $cap i32) (local $data i32)
    (local.set $len (i32.load (local.get $L)))
    (local.set $cap (i32.load offset=4 (local.get $L)))
    (if (i32.ge_s (local.get $len) (local.get $cap))
      (then (call $id_list_grow (local.get $L))))
    (local.set $data (i32.load offset=8 (local.get $L)))
    (i64.store (i32.add (local.get $data) (i32.mul (local.get $len) (i32.const 8)))
               (local.get $v))
    (i32.store (local.get $L) (i32.add (local.get $len) (i32.const 1))))

  (func $id_list_get (param $L i32) (param $idx i32) (result i64)
    (local $len i32) (local $data i32)
    (local.set $len (i32.load (local.get $L)))
    (if (i32.or (i32.lt_s (local.get $idx) (i32.const 0))
                (i32.ge_s (local.get $idx) (local.get $len)))
      (then (call $id_index_error (local.get $idx) (local.get $len)) (unreachable)))
    (local.set $data (i32.load offset=8 (local.get $L)))
    (i64.load (i32.add (local.get $data) (i32.mul (local.get $idx) (i32.const 8)))))

  (func $id_list_set (param $L i32) (param $idx i32) (param $v i64)
    (local $len i32) (local $data i32)
    (local.set $len (i32.load (local.get $L)))
    (if (i32.or (i32.lt_s (local.get $idx) (i32.const 0))
                (i32.ge_s (local.get $idx) (local.get $len)))
      (then (call $id_index_error (local.get $idx) (local.get $len)) (unreachable)))
    (local.set $data (i32.load offset=8 (local.get $L)))
    (i64.store (i32.add (local.get $data) (i32.mul (local.get $idx) (i32.const 8)))
               (local.get $v)))

  (func $id_list_len (param $L i32) (result i32)
    (i32.load (local.get $L)))

  (func $id_list_pop (param $L i32) (result i64)
    (local $len i32) (local $data i32)
    (local.set $len (i32.load (local.get $L)))
    (if (i32.le_s (local.get $len) (i32.const 0))
      (then (call $id_pop_error) (unreachable)))
    (local.set $len (i32.sub (local.get $len) (i32.const 1)))
    (i32.store (local.get $L) (local.get $len))
    (local.set $data (i32.load offset=8 (local.get $L)))
    (i64.load (i32.add (local.get $data) (i32.mul (local.get $len) (i32.const 8)))))

  (func $id_strlen (param $s i32) (result i32)
    (local $i i32)
    (local.set $i (i32.const 0))
    (block $done
      (loop $again
        (br_if $done (i32.eqz (i32.load8_u (i32.add (local.get $s) (local.get $i)))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $again)))
    (local.get $i))

  (func $id_len (param $s i32) (result i32)
    (call $id_strlen (local.get $s)))

  (func $id_concat (param $a i32) (param $b i32) (result i32)
    (local $la i32) (local $lb i32) (local $r i32)
    (local.set $la (call $id_strlen (local.get $a)))
    (local.set $lb (call $id_strlen (local.get $b)))
    (local.set $r (call $id_alloc (i32.add (i32.add (local.get $la) (local.get $lb))
                                            (i32.const 1))))
    (call $id_memcopy (local.get $r) (local.get $a) (local.get $la))
    (call $id_memcopy (i32.add (local.get $r) (local.get $la)) (local.get $b) (local.get $lb))
    (i32.store8 (i32.add (i32.add (local.get $r) (local.get $la)) (local.get $lb))
                (i32.const 0))
    (local.get $r))

  (func $id_strcmp (param $a i32) (param $b i32) (result i32)
    (local $i i32) (local $ca i32) (local $cb i32)
    (local.set $i (i32.const 0))
    (block $done
      (loop $again
        (local.set $ca (i32.load8_u (i32.add (local.get $a) (local.get $i))))
        (local.set $cb (i32.load8_u (i32.add (local.get $b) (local.get $i))))
        (br_if $done (i32.ne (local.get $ca) (local.get $cb)))
        (br_if $done (i32.eqz (local.get $ca)))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $again)))
    (i32.sub (local.get $ca) (local.get $cb)))

  (func $id_str_of_int (param $x i32) (result i32)
    (local $n i32) (local $neg i32) (local $i i32) (local $r i32) (local $j i32) (local $d i32)
    (local.set $n (local.get $x))
    (local.set $neg (i32.const 0))
    (if (i32.lt_s (local.get $n) (i32.const 0))
      (then (local.set $neg (i32.const 1))
            (local.set $n (i32.sub (i32.const 0) (local.get $n)))))
    (local.set $i (i32.const 0))
    (if (i32.eqz (local.get $n))
      (then
        (i32.store8 (i32.add (i32.const {_STROI_BUF}) (local.get $i)) (i32.const 48))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))))
    (block $digits_done
      (loop $digits
        (br_if $digits_done (i32.eqz (local.get $n)))
        (local.set $d (i32.rem_s (local.get $n) (i32.const 10)))
        (i32.store8 (i32.add (i32.const {_STROI_BUF}) (local.get $i))
                    (i32.add (local.get $d) (i32.const 48)))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (local.set $n (i32.div_s (local.get $n) (i32.const 10)))
        (br $digits)))
    (if (local.get $neg)
      (then
        (i32.store8 (i32.add (i32.const {_STROI_BUF}) (local.get $i)) (i32.const 45))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))))
    (local.set $r (call $id_alloc (i32.add (local.get $i) (i32.const 1))))
    (local.set $j (i32.const 0))
    (block $rev_done
      (loop $rev
        (br_if $rev_done (i32.ge_s (local.get $j) (local.get $i)))
        (i32.store8 (i32.add (local.get $r) (local.get $j))
                    (i32.load8_u (i32.add (i32.const {_STROI_BUF})
                                          (i32.sub (i32.sub (local.get $i) (local.get $j))
                                                    (i32.const 1)))))
        (local.set $j (i32.add (local.get $j) (i32.const 1)))
        (br $rev)))
    (i32.store8 (i32.add (local.get $r) (local.get $i)) (i32.const 0))
    (local.get $r))

  (func $id_to_int (param $s i32) (result i32)
    (local $i i32) (local $neg i32) (local $r i32) (local $c i32)
    (local.set $i (i32.const 0))
    (local.set $neg (i32.const 0))
    (local.set $r (i32.const 0))
    (block $skipws_done
      (loop $skipws
        (br_if $skipws_done (i32.ne (i32.load8_u (i32.add (local.get $s) (local.get $i)))
                                     (i32.const 32)))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $skipws)))
    (local.set $c (i32.load8_u (i32.add (local.get $s) (local.get $i))))
    (if (i32.eq (local.get $c) (i32.const 45))
      (then (local.set $neg (i32.const 1)) (local.set $i (i32.add (local.get $i) (i32.const 1))))
      (else (if (i32.eq (local.get $c) (i32.const 43))
        (then (local.set $i (i32.add (local.get $i) (i32.const 1)))))))
    (block $digits_done
      (loop $digits
        (local.set $c (i32.load8_u (i32.add (local.get $s) (local.get $i))))
        (br_if $digits_done (i32.or (i32.lt_u (local.get $c) (i32.const 48))
                                     (i32.gt_u (local.get $c) (i32.const 57))))
        (local.set $r (i32.add (i32.mul (local.get $r) (i32.const 10))
                                (i32.sub (local.get $c) (i32.const 48))))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $digits)))
    (if (local.get $neg) (then (local.set $r (i32.sub (i32.const 0) (local.get $r)))))
    (local.get $r))

  (func $id_charat (param $s i32) (param $idx i32) (result i32)
    (local $n i32)
    (local.set $n (call $id_strlen (local.get $s)))
    (if (i32.or (i32.lt_s (local.get $idx) (i32.const 0))
                (i32.ge_s (local.get $idx) (local.get $n)))
      (then (return (i32.const -1))))
    (i32.load8_u (i32.add (local.get $s) (local.get $idx))))

  (func $id_chr (param $c i32) (result i32)
    (local $r i32)
    (local.set $r (call $id_alloc (i32.const 2)))
    (i32.store8 (local.get $r) (local.get $c))
    (i32.store8 (i32.add (local.get $r) (i32.const 1)) (i32.const 0))
    (local.get $r))

  (func $id_print (param $s i32)
    (local $n i32)
    (local.set $n (call $id_strlen (local.get $s)))
    (call $id_write_all (i32.const 1) (local.get $s) (local.get $n))
    (call $id_write_all (i32.const 1) (i32.const {_NEWLINE_BYTE}) (i32.const 1)))

  (func $id_input (result i32)
    (local $n i32) (local $r i32) (local $got i32)
    (local.set $n (i32.const 0))
    (i32.store (i32.const {_READ_IOV_PTR}) (i32.const {_READ_BYTE}))
    (i32.store (i32.const {_READ_IOV_LEN}) (i32.const 1))
    (block $loop_done
      (loop $readloop
        (br_if $loop_done (i32.ge_s (local.get $n) (i32.const 1023)))
        (drop (call $fd_read (i32.const 0) (i32.const {_READ_IOV_PTR}) (i32.const 1)
                              (i32.const {_READ_NREAD})))
        (local.set $got (i32.load (i32.const {_READ_NREAD})))
        (br_if $loop_done (i32.eqz (local.get $got)))
        (br_if $loop_done (i32.eq (i32.load8_u (i32.const {_READ_BYTE})) (i32.const 10)))
        (i32.store8 (i32.add (i32.const {_INPUT_BUF}) (local.get $n))
                    (i32.load8_u (i32.const {_READ_BYTE})))
        (local.set $n (i32.add (local.get $n) (i32.const 1)))
        (br $readloop)))
    (local.set $r (call $id_alloc (i32.add (local.get $n) (i32.const 1))))
    (call $id_memcopy (local.get $r) (i32.const {_INPUT_BUF}) (local.get $n))
    (i32.store8 (i32.add (local.get $r) (local.get $n)) (i32.const 0))
    (local.get $r))

  (func $id_read_all (result i32)
    (local $cap i32) (local $n i32) (local $buf i32) (local $nbuf i32)
    (local $got i32) (local $r i32)
    (local.set $cap (i32.const 256))
    (local.set $n (i32.const 0))
    (local.set $buf (call $id_alloc (local.get $cap)))
    (i32.store (i32.const {_READ_IOV_PTR}) (i32.const {_READ_BYTE}))
    (i32.store (i32.const {_READ_IOV_LEN}) (i32.const 1))
    (block $loop_done
      (loop $readloop
        (drop (call $fd_read (i32.const 0) (i32.const {_READ_IOV_PTR}) (i32.const 1)
                              (i32.const {_READ_NREAD})))
        (local.set $got (i32.load (i32.const {_READ_NREAD})))
        (br_if $loop_done (i32.eqz (local.get $got)))
        (if (i32.ge_s (local.get $n) (local.get $cap))
          (then
            (local.set $nbuf (call $id_alloc (i32.mul (local.get $cap) (i32.const 2))))
            (call $id_memcopy (local.get $nbuf) (local.get $buf) (local.get $cap))
            (local.set $buf (local.get $nbuf))
            (local.set $cap (i32.mul (local.get $cap) (i32.const 2)))))
        (i32.store8 (i32.add (local.get $buf) (local.get $n))
                    (i32.load8_u (i32.const {_READ_BYTE})))
        (local.set $n (i32.add (local.get $n) (i32.const 1)))
        (br $readloop)))
    (local.set $r (call $id_alloc (i32.add (local.get $n) (i32.const 1))))
    (call $id_memcopy (local.get $r) (local.get $buf) (local.get $n))
    (i32.store8 (i32.add (local.get $r) (local.get $n)) (i32.const 0))
    (local.get $r))
"""


class WasmBackend:
    """Emits one WebAssembly text (WAT) module for a checked program. Shares
    the Compiler's checked tables the same way LLVMBackend does; see the
    module comment above for the value representation and scope."""

    def __init__(self, compiler: Compiler):
        self.compiler = compiler
        self.str_table = {}    # bytes -> address
        self.next_addr = _RESERVED_END

    def wtype(self, typ):
        if typ == "int":
            return "i32"
        if typ == "float":
            return "f64"
        return "i32"   # string, or any list type: an address

    def str_const(self, raw: str) -> int:
        bs = unescape_id_string(raw)
        addr = self.str_table.get(bs)
        if addr is None:
            addr = self.next_addr
            self.str_table[bs] = addr
            self.next_addr += len(bs) + 1
        return addr

    def new_temp_local(self, wt) -> str:
        self.tmp_local_n += 1
        name = f"$tmp{self.tmp_local_n}"
        self.pending_locals.append((name, wt))
        return name

    def new_lbl_id(self) -> int:
        self.lbl_n += 1
        return self.lbl_n

    def coerce(self, val, have, want):
        if have == want:
            return val
        if have == "int" and want == "float":
            return f"(f64.convert_i32_s {val})"
        return val

    def box(self, val, typ):
        if typ == "int":
            return f"(i64.extend_i32_s {val})"
        if typ == "float":
            return f"(i64.reinterpret_f64 {val})"
        return f"(i64.extend_i32_u {val})"   # string/list address

    def unbox(self, val, typ):
        if typ == "int":
            return f"(i32.wrap_i64 {val})"
        if typ == "float":
            return f"(f64.reinterpret_i64 {val})"
        return f"(i32.wrap_i64 {val})"

    def to_bool(self, val, typ):
        """A folded i32 expression that is nonzero iff `val` (of id type
        `typ`) is truthy -- used directly as an `if`/`br_if` condition (wasm's
        `if` pops an i32 and treats nonzero as true, so an int value can be
        used as-is)."""
        if typ == "int":
            return val
        if typ == "float":
            return f"(f64.ne {val} (f64.const 0))"
        return f"(i32.ne {val} (i32.const 0))"

    def to_string(self, val, typ, e):
        if typ == "string":
            return val
        if typ == "int":
            return f"(call $id_str_of_int {val})"
        raise CompileError(e.file, e.line,
                           f"cannot convert {typ} to string for --target wasm "
                           f"(float-to-string is not implemented for this target)")

    # -- statements: returns a list of indented WAT instruction lines

    def gen_stmt(self, stmt, fn, env, indent):
        ind = "  " * indent
        if isinstance(stmt, DeclStmt):
            val, typ = self.gen_expr(stmt.expr, fn, env, stmt.typ)
            if not compatible(stmt.typ, typ):
                raise CompileError(stmt.file, stmt.line,
                                   f"cannot initialize {stmt.typ} '{stmt.name}' "
                                   f"with a {typ} value")
            val = self.coerce(val, typ, stmt.typ)
            return [f"{ind}({self.setter(stmt.name)} {val})"]
        if isinstance(stmt, AssignStmt):
            if stmt.name not in env:
                self.compiler.explain_bad_var(stmt.name, fn, stmt.file, stmt.line)
            want = env[stmt.name]
            val, typ = self.gen_expr(stmt.expr, fn, env, want)
            if not compatible(want, typ):
                raise CompileError(stmt.file, stmt.line,
                                   f"cannot assign a {typ} value to {want} "
                                   f"'{stmt.name}'")
            val = self.coerce(val, typ, want)
            return [f"{ind}({self.setter(stmt.name)} {val})"]
        if isinstance(stmt, IndexAssignStmt):
            base, btyp = self.gen_expr(stmt.base, fn, env)
            if not btyp.endswith("[]"):
                raise CompileError(stmt.file, stmt.line, f"cannot index a {btyp}")
            idx, ityp = self.gen_expr(stmt.index, fn, env)
            if ityp != "int":
                raise CompileError(stmt.file, stmt.line,
                                   f"list index must be int, got {ityp}")
            elem = btyp[:-2]
            val, typ = self.gen_expr(stmt.expr, fn, env, elem)
            if not compatible(elem, typ):
                raise CompileError(stmt.file, stmt.line,
                                   f"cannot store a {typ} into a {btyp}")
            val = self.coerce(val, typ, elem)
            boxed = self.box(val, elem)
            return [f"{ind}(call $id_list_set {base} {idx} {boxed})"]
        if isinstance(stmt, IfStmt):
            cond, ctyp = self.gen_expr(stmt.cond, fn, env)
            if ctyp == "void":
                raise CompileError(stmt.file, stmt.line, "condition has type void")
            out = [f"{ind}(if {self.to_bool(cond, ctyp)}", f"{ind}  (then"]
            for s in stmt.then:
                out.extend(self.gen_stmt(s, fn, env, indent + 2))
            out.append(f"{ind}  )")
            if stmt.els is not None:
                out.append(f"{ind}  (else")
                if isinstance(stmt.els, IfStmt):
                    out.extend(self.gen_stmt(stmt.els, fn, env, indent + 2))
                else:
                    for s in stmt.els:
                        out.extend(self.gen_stmt(s, fn, env, indent + 2))
                out.append(f"{ind}  )")
            out.append(f"{ind})")
            return out
        if isinstance(stmt, WhileStmt):
            cond, ctyp = self.gen_expr(stmt.cond, fn, env)
            if ctyp == "void":
                raise CompileError(stmt.file, stmt.line, "loop condition has type void")
            n = self.new_lbl_id()
            out = [f"{ind}(block $break{n}", f"{ind}  (loop $continue{n}",
                   f"{ind}    (br_if $break{n} (i32.eqz {self.to_bool(cond, ctyp)}))"]
            for s in stmt.body:
                out.extend(self.gen_stmt(s, fn, env, indent + 2))
            out.append(f"{ind}    (br $continue{n})")
            out.append(f"{ind}  )")
            out.append(f"{ind})")
            return out
        if isinstance(stmt, ExprStmt):
            val, typ = self.gen_expr(stmt.expr, fn, env)
            if typ == "void":
                return [f"{ind}{val}"]
            return [f"{ind}(drop {val})"]
        raise AssertionError(stmt)

    def setter(self, name):
        if name in self.compiler.exported:
            return f"global.set $g_{name}"
        return f"local.set $v_{name}"

    # -- expressions: returns (wat_expr, id_type); `wat_expr` is always a
    #    single, complete, folded s-expression producing exactly one value
    #    (or none, for a void-typed call)

    def gen_expr(self, e, fn, env, expected=None):
        if isinstance(e, IntLit):
            return f"(i32.const {e.value})", "int"
        if isinstance(e, FloatLit):
            return f"(f64.const {e.value})", "float"
        if isinstance(e, StrLit):
            return f"(i32.const {self.str_const(e.raw)})", "string"
        if isinstance(e, VarRef):
            if e.name not in env:
                self.compiler.explain_bad_var(e.name, fn, e.file, e.line)
            typ = env[e.name]
            if e.name in self.compiler.exported:
                return f"(global.get $g_{e.name})", typ
            return f"(local.get $v_{e.name})", typ
        if isinstance(e, ImportRef):
            if e.name not in self.compiler.exported:
                if e.name in self.compiler.var_owner:
                    owner = self.compiler.var_owner[e.name][0]
                    raise CompileError(e.file, e.line,
                                       f"variable '{e.name}' (in function '{owner}') "
                                       f"is not exported")
                raise CompileError(e.file, e.line,
                                   f"no exported variable named '{e.name}'")
            typ = self.compiler.exported[e.name][0]
            return f"(global.get $g_{e.name})", typ
        if isinstance(e, IndexExpr):
            base, btyp = self.gen_expr(e.base, fn, env)
            if not btyp.endswith("[]"):
                raise CompileError(e.file, e.line, f"cannot index a {btyp}")
            idx, ityp = self.gen_expr(e.index, fn, env)
            if ityp != "int":
                raise CompileError(e.file, e.line, f"array index must be int, got {ityp}")
            elem = btyp[:-2]
            cell = f"(call $id_list_get {base} {idx})"
            return self.unbox(cell, elem), elem
        if isinstance(e, ArrayLit):
            if not e.elems:
                if expected is None or not expected.endswith("[]"):
                    raise CompileError(e.file, e.line,
                                       "an empty list literal needs a known list "
                                       "type here (e.g. on a typed declaration)")
                return "(call $id_list_new)", expected
            raw, etyp = [], None
            for el in e.elems:
                val, typ = self.gen_expr(el, fn, env)
                if etyp is None:
                    etyp = typ
                elif not compatible(etyp, typ):
                    raise CompileError(el.file, el.line,
                                       f"list element has type {typ}, expected {etyp}")
                if is_numeric(etyp) and typ == "float":
                    etyp = "float"
                raw.append((val, typ))
            t = self.new_temp_local("i32")
            lines = ["(block (result i32)", f"  (local.set {t} (call $id_list_new))"]
            for val, typ in raw:
                val = self.coerce(val, typ, etyp)
                boxed = self.box(val, etyp)
                lines.append(f"  (call $id_list_push (local.get {t}) {boxed})")
            lines.append(f"  (local.get {t}))")
            return "\n      ".join(lines), etyp + "[]"
        if isinstance(e, CallExpr):
            return self.gen_call(e, fn, env)
        if isinstance(e, UnOp):
            val, typ = self.gen_expr(e.operand, fn, env)
            if e.op == "-":
                if not is_numeric(typ):
                    raise CompileError(e.file, e.line, f"cannot negate a {typ}")
                if typ == "int":
                    return f"(i32.sub (i32.const 0) {val})", "int"
                return f"(f64.neg {val})", "float"
            if e.op == "!":
                if typ != "int":
                    raise CompileError(e.file, e.line, f"cannot apply '!' to a {typ}")
                return f"(i32.eqz {val})", "int"
            raise AssertionError(e.op)
        if isinstance(e, BinOp):
            return self.gen_binop(e, fn, env)
        raise AssertionError(e)

    def gen_binop(self, e: BinOp, fn, env):
        lc, lt = self.gen_expr(e.left, fn, env)
        rc, rt = self.gen_expr(e.right, fn, env)
        op = e.op
        if op == "+" and (lt == "string" or rt == "string"):
            ls = self.to_string(lc, lt, e.left)
            rs = self.to_string(rc, rt, e.right)
            return f"(call $id_concat {ls} {rs})", "string"
        if op in ("==", "!="):
            if lt == "string" and rt == "string":
                inner = f"(call $id_strcmp {lc} {rc})"
                if op == "==":
                    return f"(i32.eqz {inner})", "int"
                return f"(i32.ne {inner} (i32.const 0))", "int"
            if is_numeric(lt) and is_numeric(rt):
                common = "float" if "float" in (lt, rt) else "int"
                lc2, rc2 = self.coerce(lc, lt, common), self.coerce(rc, rt, common)
                instr = {"int": {"==": "i32.eq", "!=": "i32.ne"},
                         "float": {"==": "f64.eq", "!=": "f64.ne"}}[common][op]
                return f"({instr} {lc2} {rc2})", "int"
            raise CompileError(e.file, e.line, f"cannot compare {lt} with {rt}")
        if op in ("<", "<=", ">", ">="):
            if is_numeric(lt) and is_numeric(rt):
                common = "float" if "float" in (lt, rt) else "int"
                lc2, rc2 = self.coerce(lc, lt, common), self.coerce(rc, rt, common)
                imap = {"<": "i32.lt_s", "<=": "i32.le_s", ">": "i32.gt_s", ">=": "i32.ge_s"}
                fmap = {"<": "f64.lt", "<=": "f64.le", ">": "f64.gt", ">=": "f64.ge"}
                instr = imap[op] if common == "int" else fmap[op]
                return f"({instr} {lc2} {rc2})", "int"
            raise CompileError(e.file, e.line, f"cannot order {lt} and {rt}")
        if op in ("&&", "||"):
            if lt == "int" and rt == "int":
                lb = f"(i32.ne {lc} (i32.const 0))"
                rb = f"(i32.ne {rc} (i32.const 0))"
                instr = "i32.and" if op == "&&" else "i32.or"
                return f"({instr} {lb} {rb})", "int"
            raise CompileError(e.file, e.line, f"'{op}' requires int operands")
        if op in ("+", "-", "*", "/", "%"):
            if is_numeric(lt) and is_numeric(rt):
                if op == "%" and (lt == "float" or rt == "float"):
                    raise CompileError(e.file, e.line, "'%' requires int operands")
                res = "float" if "float" in (lt, rt) else "int"
                lc2, rc2 = self.coerce(lc, lt, res), self.coerce(rc, rt, res)
                if res == "int":
                    instr = {"+": "i32.add", "-": "i32.sub", "*": "i32.mul",
                             "/": "i32.div_s", "%": "i32.rem_s"}[op]
                else:
                    instr = {"+": "f64.add", "-": "f64.sub", "*": "f64.mul",
                             "/": "f64.div"}[op]
                return f"({instr} {lc2} {rc2})", res
            raise CompileError(e.file, e.line, f"cannot apply '{op}' to {lt} and {rt}")
        raise AssertionError(op)

    def gen_call(self, e: CallExpr, fn, env):
        name = e.name
        if name == "print":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "print takes exactly one argument")
            val, typ = self.gen_expr(e.args[0], fn, env)
            s = self.to_string(val, typ, e)
            return f"(call $id_print {s})", "void"
        if name == "input":
            if e.args:
                raise CompileError(e.file, e.line, "input takes no arguments")
            return "(call $id_input)", "string"
        if name == "read_all":
            if e.args:
                raise CompileError(e.file, e.line, "read_all takes no arguments")
            return "(call $id_read_all)", "string"
        if name == "len":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "len takes exactly one argument")
            val, typ = self.gen_expr(e.args[0], fn, env)
            if typ == "string":
                return f"(call $id_len {val})", "int"
            if typ.endswith("[]"):
                return f"(call $id_list_len {val})", "int"
            raise CompileError(e.file, e.line, f"len expects a string or list, got {typ}")
        if name == "push":
            if len(e.args) != 2:
                raise CompileError(e.file, e.line, "push takes exactly two arguments")
            lc, lt = self.gen_expr(e.args[0], fn, env)
            if not lt.endswith("[]"):
                raise CompileError(e.file, e.line, f"push expects a list, got {lt}")
            elem = lt[:-2]
            vc, vt = self.gen_expr(e.args[1], fn, env, elem)
            if not compatible(elem, vt):
                raise CompileError(e.file, e.line, f"cannot push a {vt} onto a {lt}")
            vc = self.coerce(vc, vt, elem)
            boxed = self.box(vc, elem)
            return f"(call $id_list_push {lc} {boxed})", "void"
        if name == "pop":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "pop takes exactly one argument")
            lc, lt = self.gen_expr(e.args[0], fn, env)
            if not lt.endswith("[]"):
                raise CompileError(e.file, e.line, f"pop expects a list, got {lt}")
            elem = lt[:-2]
            return self.unbox(f"(call $id_list_pop {lc})", elem), elem
        if name == "to_int":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "to_int takes exactly one argument")
            val, typ = self.gen_expr(e.args[0], fn, env)
            if typ != "string":
                raise CompileError(e.file, e.line, f"to_int expects a string, got {typ}")
            return f"(call $id_to_int {val})", "int"
        if name == "charat":
            if len(e.args) != 2:
                raise CompileError(e.file, e.line, "charat takes exactly two arguments")
            sc, st = self.gen_expr(e.args[0], fn, env)
            ic, it = self.gen_expr(e.args[1], fn, env)
            if st != "string":
                raise CompileError(e.file, e.line, f"charat expects a string, got {st}")
            if it != "int":
                raise CompileError(e.file, e.line, f"charat index must be int, got {it}")
            return f"(call $id_charat {sc} {ic})", "int"
        if name == "chr":
            if len(e.args) != 1:
                raise CompileError(e.file, e.line, "chr takes exactly one argument")
            val, typ = self.gen_expr(e.args[0], fn, env)
            if typ != "int":
                raise CompileError(e.file, e.line, f"chr expects an int, got {typ}")
            return f"(call $id_chr {val})", "string"
        if name in UNSUPPORTED_BUILTINS:
            raise CompileError(e.file, e.line,
                               f"builtin '{name}' is not supported for this "
                               f"--target (real-time I/O is C-only)")
        args = [self.gen_expr(a, fn, env) for a in e.args]
        callee = self.compiler.funcs.get(name)
        if callee is None:
            raise CompileError(e.file, e.line,
                               f"call to external function '{name}' is not "
                               f"supported for this --target (only functions "
                               f"defined in the program are supported)."
                               f"{builtin_hint(name)}")
        if len(args) != len(callee.params):
            raise CompileError(e.file, e.line,
                               f"function '{name}' takes {len(callee.params)} "
                               f"argument(s), got {len(args)}")
        argstrs = []
        for (ptype, pname), (val, typ), arg in zip(callee.params, args, e.args):
            if not compatible(ptype, typ):
                raise CompileError(arg.file, arg.line,
                                   f"argument '{pname}' of '{name}' expects "
                                   f"{ptype}, got {typ}")
            argstrs.append(self.coerce(val, typ, ptype))
        rettype = callee.rettype
        return f"(call $id_{name} {' '.join(argstrs)})", rettype

    # -- function codegen

    def gen_function(self, fn: FuncDef) -> str:
        env = self.compiler.build_env(fn)
        param_names = {n for _, n in fn.params}
        self.pending_locals = []
        self.tmp_local_n = 0
        self.lbl_n = 0

        body_lines = []
        for stmt in fn.body:
            body_lines.extend(self.gen_stmt(stmt, fn, env, 2))
        tail = []
        if fn.rettype != "void":
            val, typ = self.gen_expr(fn.retexpr, fn, env)
            if not compatible(fn.rettype, typ):
                raise CompileError(fn.retexpr.file, fn.retexpr.line,
                                   f"function '{fn.name}' returns {fn.rettype} but "
                                   f"the expression has type {typ}")
            val = self.coerce(val, typ, fn.rettype)
            tail = [f"    (return {val})"]

        params = " ".join(f"(param $v_{n} {self.wtype(t)})" for t, n in fn.params)
        result = "" if fn.rettype == "void" else f" (result {self.wtype(fn.rettype)})"
        locals_decl = []
        for name, typ in env.items():
            if name in self.compiler.exported or name in param_names:
                continue
            locals_decl.append(f"    (local $v_{name} {self.wtype(typ)})")
        for name, wt in self.pending_locals:
            locals_decl.append(f"    (local {name} {wt})")

        lines = [f"  (func $id_{fn.name} {params}{result}"]
        lines.extend(locals_decl)
        lines.extend(body_lines)
        lines.extend(tail)
        lines.append("  )")
        return "\n".join(lines)

    def gen_entrypoint(self) -> str:
        m = self.compiler.funcs.get("main")
        if m is None:
            return ""
        ptypes = [t for t, _ in m.params]
        lines = ['  (func $_start (export "_start")']
        if ptypes == ["int", "string[]"]:
            lines += [
                "    (local $argc i32) (local $bufsize i32) (local $i i32)",
                "    (local $ptrs i32) (local $buf i32) (local $args i32)",
                f"    (drop (call $args_sizes_get (i32.const {_ARGC_SCRATCH}) "
                f"(i32.const {_BUFSIZE_SCRATCH})))",
                f"    (local.set $argc (i32.load (i32.const {_ARGC_SCRATCH})))",
                f"    (local.set $bufsize (i32.load (i32.const {_BUFSIZE_SCRATCH})))",
                "    (local.set $ptrs (call $id_alloc (i32.mul (local.get $argc) (i32.const 4))))",
                "    (local.set $buf (call $id_alloc (local.get $bufsize)))",
                "    (drop (call $args_get (local.get $ptrs) (local.get $buf)))",
                "    (local.set $args (call $id_list_new))",
                "    (local.set $i (i32.const 0))",
                "    (block $argdone",
                "      (loop $argloop",
                "        (br_if $argdone (i32.ge_s (local.get $i) (local.get $argc)))",
                "        (call $id_list_push (local.get $args)",
                "          (i64.extend_i32_u (i32.load (i32.add (local.get $ptrs)",
                "            (i32.mul (local.get $i) (i32.const 4))))))",
                "        (local.set $i (i32.add (local.get $i) (i32.const 1)))",
                "        (br $argloop)))",
            ]
            call_args = "(local.get $argc) (local.get $args)"
        elif ptypes == []:
            call_args = ""
        else:
            raise CompileError(m.file, m.line,
                               "main must take (int, string[]) or no parameters")
        if m.rettype == "int":
            lines.append(f"    (call $proc_exit (call $id_main {call_args}))")
        else:
            lines.append(f"    (call $id_main {call_args})")
        lines.append("  )")
        return "\n".join(lines)

    def emit_module(self) -> str:
        func_bodies = [self.gen_function(fn) for fn in self.compiler.funcs.values()]
        heap_base = ((self.next_addr + 15) // 16) * 16

        parts = ["(module"]
        parts.append('  (import "wasi_snapshot_preview1" "fd_write" '
                     '(func $fd_write (param i32 i32 i32 i32) (result i32)))')
        parts.append('  (import "wasi_snapshot_preview1" "fd_read" '
                     '(func $fd_read (param i32 i32 i32 i32) (result i32)))')
        parts.append('  (import "wasi_snapshot_preview1" "args_sizes_get" '
                     '(func $args_sizes_get (param i32 i32) (result i32)))')
        parts.append('  (import "wasi_snapshot_preview1" "args_get" '
                     '(func $args_get (param i32 i32) (result i32)))')
        parts.append('  (import "wasi_snapshot_preview1" "proc_exit" '
                     '(func $proc_exit (param i32)))')
        parts.append('  (memory (export "memory") 32)')
        parts.append(f'  (global $heap (mut i32) (i32.const {heap_base}))')
        parts.append(f'  (data (i32.const {_NEWLINE_BYTE}) "\\0a")')
        parts.append(f'  (data (i32.const {_MSG_IDX_PRE_ADDR}) "{wat_bytes_literal(_MSG_IDX_PRE)}")')
        parts.append(f'  (data (i32.const {_MSG_IDX_MID_ADDR}) "{wat_bytes_literal(_MSG_IDX_MID)}")')
        parts.append(f'  (data (i32.const {_MSG_IDX_END_ADDR}) "{wat_bytes_literal(_MSG_IDX_END)}")')
        parts.append(f'  (data (i32.const {_MSG_POP_ADDR}) "{wat_bytes_literal(_MSG_POP)}")')
        parts.append(f'  (data (i32.const {_MSG_OOM_ADDR}) "{wat_bytes_literal(_MSG_OOM)}")')
        parts.append(f'  (data (i32.const {_MSG_CAP_ADDR}) "{wat_bytes_literal(_MSG_CAP)}")')
        for bs, addr in self.str_table.items():
            parts.append(f'  (data (i32.const {addr}) "{wat_bytes_literal(bs)}")')
        for gname, (typ, owner) in self.compiler.exported.items():
            wt = self.wtype(typ)
            zero = "(i32.const 0)" if wt == "i32" else "(f64.const 0)"
            parts.append(f'  (global $g_{gname} (mut {wt}) {zero})')
        parts.append(wasm_runtime_funcs())
        parts.extend(func_bodies)
        # Export every user-defined function so an embedder (e.g. a JS host
        # driving an idml UI) can call id logic directly, and id_alloc so the
        # host can place string/byte arguments into linear memory. These are
        # additive: the WASI `_start`/`memory` exports (command-style execution
        # under wasmtime) are unaffected, so a program with a `main` still runs
        # as before while also exposing its functions to an embedder.
        for name in self.compiler.funcs:
            parts.append(f'  (export "{name}" (func $id_{name}))')
        parts.append('  (export "id_alloc" (func $id_alloc))')
        entry = self.gen_entrypoint()
        if entry:
            parts.append(entry)
        parts.append(")")
        return "\n".join(parts) + "\n"


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

# A project may declare its dependencies (native backends, other id-source
# directories) in a single manifest file at its root. It is NOT compiled as
# source and does NOT count toward a directory's entry limit -- it's metadata,
# the id-native replacement for the --backend flag. See parse_import_manifest.
IMPORT_MANIFEST = "import.id"


def collect_project(root):
    """Walk the project tree, enforce the per-directory entry limit, and return
    every .id file in deterministic (sorted full-path) order."""
    id_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # ignore hidden entries; they neither compile nor count
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        # the dependency manifest is metadata, not source: never compiled, never
        # counted toward the per-directory entry limit.
        ids = [n for n in filenames if n.endswith(".id") and n != IMPORT_MANIFEST]
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


def parse_import_manifest(root):
    """Read <root>/import.id if present and return the dependency directories it
    names. Each non-blank, non-comment line is `import "<relative-dir>"`; the
    path is resolved relative to the manifest. This is the id-native way to
    attach dependencies (replacing --backend): a dependency that carries a
    backend.json is linked as a native backend, any other directory is merged in
    as additional id source. Returns [] when there is no manifest."""
    path = os.path.join(root, IMPORT_MANIFEST)
    if not os.path.isfile(path):
        return []
    deps = []
    with open(path) as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("//"):
                continue
            m = re.match(r'^import\s+"([^"]+)"\s*$', line)
            if not m:
                raise CompileError(
                    path, lineno,
                    f'malformed import.id line: {raw.rstrip()!r}; each dependency '
                    f'is a line of the form  import "relative/dir"')
            dep = os.path.normpath(os.path.join(root, m.group(1)))
            if not os.path.isdir(dep):
                raise CompileError(
                    path, lineno,
                    f'import "{m.group(1)}" does not resolve to a directory '
                    f'(looked for {dep})')
            deps.append(dep)
    return deps


def platform_key():
    """Map sys.platform to a backend.json platform key."""
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform.startswith("linux"):
        return "linux"
    return sys.platform


def resolve_backend(dir_path, cc):
    """Read a backend dir's manifest, compile its sources for this platform, and
    return (objects, link_flags). Objects are temp .o files the caller links and
    then removes. Raises CompileError on a bad/unsupported backend."""
    manifest = os.path.join(dir_path, "backend.json")
    try:
        with open(manifest) as f:
            spec = json.load(f)
    except OSError:
        raise CompileError(dir_path, 0, f"backend has no backend.json: {manifest}")
    except ValueError as e:
        raise CompileError(manifest, 0, f"invalid backend.json: {e}")

    key = platform_key()
    plat = spec.get("platforms", {}).get(key)
    if plat is None:
        name = spec.get("name", os.path.basename(dir_path.rstrip("/")))
        raise CompileError(manifest, 0,
                           f"backend '{name}' has no support for platform '{key}'")

    objects = []
    for src in plat.get("sources", []):
        src_path = os.path.join(dir_path, src)
        obj = os.path.splitext(src_path)[0] + ".gen.o"
        cmd = [cc, "-O2", "-c", src_path, "-o", obj] + list(plat.get("cflags", []))
        res = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        if res.stderr:
            sys.stderr.write(res.stderr)
        if res.returncode != 0:
            for o in objects:
                if os.path.exists(o):
                    os.unlink(o)
            msg = f"backend compile failed (command: {' '.join(cmd)})"
            # A backend links native system libraries (OpenGL, X11, ...). On a
            # system where their dev headers/libs aren't on the compiler's
            # default search path -- notably NixOS -- the compile fails with a
            # missing-header/library error. Point the user at the dev-shell,
            # which provides them, rather than leaving a cryptic cc error.
            low = (res.stderr or "").lower()
            if ("no such file" in low or "not found" in low
                    or "fatal error" in low or os.path.exists("/etc/NIXOS")):
                bdir = dir_path.rstrip("/")
                msg += ("\n  hint: this backend links native dev libraries (OpenGL, "
                        "X11, ...) whose headers may not be on the compiler's default\n"
                        "        search path (e.g. on NixOS). Build inside the dev-shell, "
                        "which provides them:\n"
                        f"          tools/devshell.sh './idc.py YOUR_PROJECT "
                        f"--backend {bdir} -o OUT'")
            raise CompileError(src_path, 0, msg)
        objects.append(obj)
    return objects, list(plat.get("link", []))


def main(argv):
    ap = argparse.ArgumentParser(prog="idc", description="compiler for the id language")
    ap.add_argument("path",
                    help="a single .id file, or a project directory (its whole "
                         "tree of .id files is compiled together)")
    ap.add_argument("-o", "--output", help="output executable path")
    ap.add_argument("--target", choices=["c", "llvm", "wasm"], default="c",
                    help="codegen target (default: c)")
    ap.add_argument("--emit-c", metavar="FILE", help="write the generated C and stop")
    ap.add_argument("--emit-llvm", metavar="FILE",
                    help="write the generated LLVM IR (.ll) and stop (--target llvm)")
    ap.add_argument("--emit-wasm", metavar="FILE",
                    help="write the generated WebAssembly text (.wat) and stop "
                         "(--target wasm)")
    ap.add_argument("--keep-c", action="store_true",
                    help="keep the generated C next to the output")
    ap.add_argument("--cc", default="cc", help="C compiler to use (default: cc)")
    ap.add_argument("--backend", action="append", default=[], metavar="DIR",
                    help="DEPRECATED: prefer an import.id manifest in the project. "
                         "Link a native backend directory (reads its backend.json "
                         "for this platform's sources and link flags); repeatable")
    args = ap.parse_args(argv)

    try:
        if os.path.isdir(args.path):
            source_files = collect_project(args.path)
            # Dependencies declared in the project's import.id: a backend dir is
            # linked (like --backend); any other dir is merged in as id source.
            for dep in parse_import_manifest(args.path):
                if os.path.isfile(os.path.join(dep, "backend.json")):
                    args.backend.append(dep)
                else:
                    source_files.extend(collect_project(dep))
            source_files = sorted(set(source_files))
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
        compiler = Compiler(funcs_by_file, has_backend=bool(args.backend))
        if args.target == "c":
            code = compiler.compile()
        elif args.target == "llvm":
            compiler.validate()
            code = LLVMBackend(compiler).emit_module()
        else:
            compiler.validate()
            code = WasmBackend(compiler).emit_module()
    except CompileError as err:
        print(str(err), file=sys.stderr)
        return 1
    except OSError as err:
        print(f"idc: {err}", file=sys.stderr)
        return 1

    if args.target == "c" and args.emit_c:
        with open(args.emit_c, "w") as f:
            f.write(code)
        print(f"wrote {args.emit_c}")
        return 0
    if args.target == "llvm" and args.emit_llvm:
        with open(args.emit_llvm, "w") as f:
            f.write(code)
        print(f"wrote {args.emit_llvm}")
        return 0
    if args.target == "wasm" and args.emit_wasm:
        with open(args.emit_wasm, "w") as f:
            f.write(code)
        print(f"wrote {args.emit_wasm}")
        return 0

    have_main = "main" in compiler.funcs
    out = args.output
    if out is None:
        # default name: the project directory's name, or the file's stem
        first = os.path.normpath(args.path)
        base = os.path.basename(first if os.path.isdir(first)
                                else os.path.splitext(first)[0])
        out = base + (".o" if not have_main else "")

    if args.target != "c" and args.backend:
        warn(args.path, 0,
             f"--backend ignored: native graphics/real-time backends are C-only "
             f"(--target {args.target} doesn't support them)")

    if args.target == "c":
        return build_c(compiler, code, args, out, have_main)
    if args.target == "llvm":
        return build_llvm(code, args, out, have_main)
    return build_wasm(code, args, out, have_main)


def build_c(compiler, c_code, args, out, have_main):
    # Native backends link only into a real executable; a library .o has nothing
    # to link them into, so skip (with a note) when there is no main.
    backend_objs, backend_link = [], []
    if args.backend and not have_main:
        warn(args.path, 0, "--backend ignored: this project has no main (builds "
                           "to a .o); link the backend into the final program")
    elif args.backend:
        try:
            for d in args.backend:
                objs, link = resolve_backend(d, args.cc)
                backend_objs += objs
                backend_link += link
        except CompileError as err:
            for o in backend_objs:
                if os.path.exists(o):
                    os.unlink(o)
            print(str(err), file=sys.stderr)
            return 1

    c_path = (os.path.splitext(out)[0] + ".c") if args.keep_c else out + ".gen.c"
    with open(c_path, "w") as f:
        f.write(c_code)

    cmd = [args.cc, "-std=c11", "-O2", c_path] + backend_objs + ["-o", out] + backend_link
    if not have_main:
        cmd.insert(1, "-c")  # no entrypoint: produce an object file to link later
    try:
        res = subprocess.run(cmd)
    finally:
        if not args.keep_c:
            os.unlink(c_path)
        for o in backend_objs:
            if os.path.exists(o):
                os.unlink(o)
    if res.returncode != 0:
        print(f"idc: C compilation failed (command: {' '.join(cmd)})", file=sys.stderr)
        return 1
    return 0


def build_llvm(ll_code, args, out, have_main):
    """Lower the emitted LLVM IR to a native binary with clang, reusing the
    existing C `RUNTIME` (compiled by clang alongside the .ll) for lists,
    strings, and the rest of the id builtins."""
    ll_path = out + ".gen.ll"
    rt_path = out + ".gen.rt.c"
    with open(ll_path, "w") as f:
        f.write(ll_code)
    with open(rt_path, "w") as f:
        # the C target's RUNTIME marks every helper `static` (internal linkage,
        # fine when it's spliced into the single generated C file); the .ll
        # here is a *separate* translation unit that calls these functions, so
        # this copy (used only for the llvm/wasm build step -- never for
        # --target c's emitted C, which stays byte-identical) drops `static`
        # to give them external linkage.
        f.write(re.sub(r"(?m)^static ", "", RUNTIME))
    if have_main:
        cmd = ["clang", "-O2", "-Wno-override-module", rt_path, ll_path, "-o", out]
    else:
        # no entrypoint: emit an object file (its id_* runtime references stay
        # unresolved, to be linked against a runtime later, like the C target)
        cmd = ["clang", "-O2", "-Wno-override-module", "-c", ll_path, "-o", out]
    try:
        res = subprocess.run(cmd)
    finally:
        os.unlink(ll_path)
        os.unlink(rt_path)
    if res.returncode != 0:
        print(f"idc: LLVM compilation failed (command: {' '.join(cmd)})", file=sys.stderr)
        return 1
    return 0


def build_wasm(wat_code, args, out, have_main):
    """Assemble the emitted WebAssembly text with wat2wasm into a runnable
    (wasmtime-runnable, WASI command-style) module."""
    wat_path = out + ".gen.wat"
    with open(wat_path, "w") as f:
        f.write(wat_code)
    cmd = ["wat2wasm", wat_path, "-o", out]
    try:
        res = subprocess.run(cmd)
    finally:
        os.unlink(wat_path)
    if res.returncode != 0:
        print(f"idc: wasm assembly failed (command: {' '.join(cmd)})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
