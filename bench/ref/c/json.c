#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { NUL, FALSE_, TRUE_, NUM, STR, ARR, OBJ };

typedef struct Node {
    int kind;
    int slen;
    int32_t num;
    int nkids, cap;
    struct Node** kids;
    int* keylens;
} Node;

typedef struct { const char* p; size_t n, i; } Src;

static void fail(const char* m) { fprintf(stderr, "json: %s\n", m); exit(1); }

static void ws(Src* s) {
    while (s->i < s->n && (s->p[s->i] == ' ' || s->p[s->i] == '\n' || s->p[s->i] == '\r' || s->p[s->i] == '\t')) s->i++;
}

static Node* node_new(int kind) {
    Node* n = calloc(1, sizeof(Node));
    n->kind = kind;
    return n;
}

static void add_kid(Node* n, Node* k, int keylen) {
    if (n->nkids == n->cap) {
        n->cap = n->cap ? n->cap * 2 : 4;
        n->kids = realloc(n->kids, sizeof(Node*) * n->cap);
        n->keylens = realloc(n->keylens, sizeof(int) * n->cap);
    }
    n->kids[n->nkids] = k;
    n->keylens[n->nkids] = keylen;
    n->nkids++;
}

static int scan_string(Src* s) {
    s->i++;
    size_t start = s->i;
    while (s->i < s->n && s->p[s->i] != '"') {
        if (s->p[s->i] == '\\') s->i++;
        s->i++;
    }
    if (s->i >= s->n) fail("unterminated string");
    int len = (int)(s->i - start);
    s->i++;
    return len;
}

static Node* parse_value(Src* s);

static Node* parse_array(Src* s) {
    Node* n = node_new(ARR);
    s->i++;
    ws(s);
    if (s->p[s->i] == ']') { s->i++; return n; }
    for (;;) {
        ws(s);
        add_kid(n, parse_value(s), 0);
        ws(s);
        if (s->p[s->i] == ',') { s->i++; continue; }
        if (s->p[s->i] == ']') { s->i++; return n; }
        fail("expected , or ]");
    }
}

static Node* parse_object(Src* s) {
    Node* n = node_new(OBJ);
    s->i++;
    ws(s);
    if (s->p[s->i] == '}') { s->i++; return n; }
    for (;;) {
        ws(s);
        if (s->p[s->i] != '"') fail("expected key");
        int klen = scan_string(s);
        ws(s);
        if (s->p[s->i] != ':') fail("expected :");
        s->i++;
        ws(s);
        add_kid(n, parse_value(s), klen);
        ws(s);
        if (s->p[s->i] == ',') { s->i++; continue; }
        if (s->p[s->i] == '}') { s->i++; return n; }
        fail("expected , or }");
    }
}

static Node* parse_value(Src* s) {
    char c = s->p[s->i];
    if (c == '{') return parse_object(s);
    if (c == '[') return parse_array(s);
    if (c == '"') { Node* n = node_new(STR); n->slen = scan_string(s); return n; }
    if (c == 't') { s->i += 4; return node_new(TRUE_); }
    if (c == 'f') { s->i += 5; return node_new(FALSE_); }
    if (c == 'n') { s->i += 4; return node_new(NUL); }
    Node* n = node_new(NUM);
    int neg = 0;
    if (c == '-') { neg = 1; s->i++; }
    uint32_t v = 0;
    while (s->i < s->n && s->p[s->i] >= '0' && s->p[s->i] <= '9') { v = v * 10 + (uint32_t)(s->p[s->i] - '0'); s->i++; }
    n->num = (int32_t)(neg ? 0u - v : v);
    return n;
}

typedef struct { long values; uint32_t numsum; long strbytes, keybytes, trues; int maxdepth; } Stats;

static void walk(const Node* n, int depth, Stats* st) {
    st->values++;
    if (depth > st->maxdepth) st->maxdepth = depth;
    if (n->kind == NUM) st->numsum += (uint32_t)n->num;
    else if (n->kind == STR) st->strbytes += n->slen;
    else if (n->kind == TRUE_) st->trues++;
    else if (n->kind == ARR || n->kind == OBJ) {
        for (int i = 0; i < n->nkids; i++) {
            if (n->kind == OBJ) st->keybytes += n->keylens[i];
            walk(n->kids[i], depth + 1, st);
        }
    }
}

int main(int argc, char** argv) {
    (void)argc; (void)argv;
    size_t cap = 1 << 20, len = 0;
    char* buf = malloc(cap + 1);
    size_t got;
    while ((got = fread(buf + len, 1, cap - len, stdin)) > 0) {
        len += got;
        if (len == cap) { cap *= 2; buf = realloc(buf, cap + 1); }
    }
    Src s = {buf, len, 0};
    ws(&s);
    Node* root = parse_value(&s);
    ws(&s);
    if (s.i != len) fail("trailing data");
    Stats st = {0, 0, 0, 0, 0, 0};
    walk(root, 1, &st);
    printf("%ld\n%d\n%ld\n%ld\n%ld\n%d\n", st.values, (int)st.numsum, st.strbytes, st.keybytes, st.trues, st.maxdepth);
    return 0;
}
