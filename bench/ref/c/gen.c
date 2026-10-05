#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t s = 4242;

static uint32_t draw(void) {
    s = (s * 1103515245u + 12345u) & 0x7fffffffu;
    return s >> 8;
}

static void gen_json(long n) {
    putchar('[');
    for (long i = 0; i < n; i++) {
        if (i > 0) fputs(",\n", stdout);
        unsigned jid = draw() % 100000;
        unsigned jname = draw() % 1000;
        printf("{\"id\":%u,\"name\":\"user%u\",\"tags\":[", jid, jname);
        int nt = (int)(draw() % 4);
        for (int t = 0; t < nt; t++) printf("%s\"t%u\"", t ? "," : "", draw() % 100);
        printf("],\"ok\":%s,", draw() % 2 ? "true" : "false");
        int x = (int)(draw() % 1000) - 500;
        int y = (int)(draw() % 1000) - 500;
        printf("\"pos\":{\"x\":%d,\"y\":%d},", x, y);
        if (draw() % 3 == 0) fputs("\"note\":\"memo text\"}", stdout);
        else fputs("\"note\":null}", stdout);
    }
    puts("]");
}

static void gen_csv(long n) {
    puts("id,customer,qty,price");
    for (long i = 0; i < n; i++) {
        unsigned c = draw() % 20000;
        unsigned q = draw() % 20 + 1;
        unsigned p = draw() % 9999 + 1;
        printf("%ld,c%05u,%u,%u\n", i, c, q, p);
    }
}

static void gen_dna(long n) {
    const char* acgt = "ACGT";
    long col = 0;
    for (long i = 0; i < n; i++) {
        uint32_t r = draw() % 100;
        char ch = r < 30 ? 'A' : r < 50 ? 'C' : r < 70 ? 'G' : 'T';
        (void)acgt;
        putchar(ch);
        if (++col == 60) { putchar('\n'); col = 0; }
    }
    if (col) putchar('\n');
}

static void gen_expr_rec(int depth) {
    uint32_t r = draw() % 8;
    if (depth == 0 || r < 2) { printf("%u", draw() % 1000); return; }
    if (r == 2) { putchar('('); gen_expr_rec(depth - 1); putchar(')'); return; }
    gen_expr_rec(depth - 1);
    putchar("+-*/"[draw() % 4]);
    gen_expr_rec(depth - 1);
}

static void gen_expr(long n) {
    for (long i = 0; i < n; i++) { gen_expr_rec(7); putchar('\n'); }
}

int main(int argc, char** argv) {
    if (argc < 3) { fprintf(stderr, "usage: gen json|csv|dna|expr N\n"); return 2; }
    long n = atol(argv[2]);
    if (!strcmp(argv[1], "json")) gen_json(n);
    else if (!strcmp(argv[1], "csv")) gen_csv(n);
    else if (!strcmp(argv[1], "dna")) gen_dna(n);
    else if (!strcmp(argv[1], "expr")) gen_expr(n);
    else return 2;
    return 0;
}
