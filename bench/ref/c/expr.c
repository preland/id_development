#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define MASK 1048575u

typedef struct { const char* p; size_t i, end; } Cur;

static uint32_t parse_expr(Cur* c);

static uint32_t parse_factor(Cur* c) {
    if (c->p[c->i] == '(') {
        c->i++;
        uint32_t v = parse_expr(c);
        c->i++;
        return v;
    }
    uint32_t v = 0;
    while (c->i < c->end && c->p[c->i] >= '0' && c->p[c->i] <= '9') { v = v * 10 + (uint32_t)(c->p[c->i] - '0'); c->i++; }
    return v & MASK;
}

static uint32_t parse_term(Cur* c) {
    uint32_t f = parse_factor(c);
    while (c->i < c->end && (c->p[c->i] == '*' || c->p[c->i] == '/')) {
        char op = c->p[c->i++];
        uint32_t g = parse_factor(c);
        if (op == '*') f = (f * g) & MASK;
        else f = g == 0 ? 0 : f / g;
    }
    return f;
}

static uint32_t parse_expr(Cur* c) {
    uint32_t t = parse_term(c);
    while (c->i < c->end && (c->p[c->i] == '+' || c->p[c->i] == '-')) {
        char op = c->p[c->i++];
        uint32_t u = parse_term(c);
        if (op == '+') t = (t + u) & MASK;
        else t = (t - u) & MASK;
    }
    return t;
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
    uint32_t total = 0;
    long lines = 0;
    size_t i = 0;
    while (i < len) {
        size_t e = i;
        while (e < len && buf[e] != '\n') e++;
        Cur c = {buf, i, e};
        total += parse_expr(&c);
        lines++;
        i = e + 1;
    }
    printf("%ld\n%d\n", lines, (int)total);
    return 0;
}
