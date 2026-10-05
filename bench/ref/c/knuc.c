#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { const char* key; int len; uint32_t count; } Slot;
typedef struct { Slot* slots; size_t cap; size_t used; } Table;

static uint32_t hash_bytes(const char* p, int n) {
    uint32_t h = 2166136261u;
    for (int i = 0; i < n; i++) { h ^= (unsigned char)p[i]; h *= 16777619u; }
    return h;
}

static void table_init(Table* t) {
    t->cap = 1024; t->used = 0;
    t->slots = calloc(t->cap, sizeof(Slot));
}

static void table_add(Table* t, const char* key, int len);

static void table_grow(Table* t) {
    Slot* old = t->slots;
    size_t oc = t->cap;
    t->cap *= 2;
    t->slots = calloc(t->cap, sizeof(Slot));
    t->used = 0;
    for (size_t i = 0; i < oc; i++) {
        if (old[i].key) {
            size_t h = hash_bytes(old[i].key, old[i].len) & (t->cap - 1);
            while (t->slots[h].key) h = (h + 1) & (t->cap - 1);
            t->slots[h] = old[i];
            t->used++;
        }
    }
    free(old);
}

static void table_add(Table* t, const char* key, int len) {
    if (t->used * 2 >= t->cap) table_grow(t);
    size_t h = hash_bytes(key, len) & (t->cap - 1);
    for (;;) {
        Slot* s = &t->slots[h];
        if (!s->key) { s->key = key; s->len = len; s->count = 1; t->used++; return; }
        if (s->len == len && memcmp(s->key, key, len) == 0) { s->count++; return; }
        h = (h + 1) & (t->cap - 1);
    }
}

static uint32_t table_get(const Table* t, const char* key, int len) {
    size_t h = hash_bytes(key, len) & (t->cap - 1);
    for (;;) {
        const Slot* s = &t->slots[h];
        if (!s->key) return 0;
        if (s->len == len && memcmp(s->key, key, len) == 0) return s->count;
        h = (h + 1) & (t->cap - 1);
    }
}

static void count_all(Table* t, const char* seq, int n, int k) {
    table_init(t);
    for (int i = 0; i + k <= n; i++) table_add(t, seq + i, k);
}

static int slot_before(const Slot* a, const Slot* b) {
    if (a->count != b->count) return a->count > b->count;
    return memcmp(a->key, b->key, a->len) < 0;
}

static void report(const Table* t, int k, int total) {
    int n = 0;
    Slot** v = malloc(sizeof(Slot*) * t->cap);
    for (size_t i = 0; i < t->cap; i++) if (t->slots[i].key) v[n++] = &t->slots[i];
    for (int i = 1; i < n; i++) {
        Slot* x = v[i];
        int j = i - 1;
        while (j >= 0 && slot_before(x, v[j])) { v[j + 1] = v[j]; j--; }
        v[j + 1] = x;
    }
    for (int i = 0; i < n; i++) {
        long long pct = (long long)v[i]->count * 100000 / total;
        printf("%.*s %lld.%03lld\n", k, v[i]->key, pct / 1000, pct % 1000);
    }
    printf("\n");
    free(v);
}

int main(int argc, char** argv) {
    (void)argc; (void)argv;
    size_t cap = 1 << 20, len = 0;
    char* buf = malloc(cap);
    size_t got;
    while ((got = fread(buf + len, 1, cap - len, stdin)) > 0) {
        len += got;
        if (len == cap) { cap *= 2; buf = realloc(buf, cap); }
    }
    int n = 0;
    char* seq = malloc(len + 1);
    for (size_t i = 0; i < len; i++) if (buf[i] != '\n') seq[n++] = buf[i];
    Table t;
    for (int k = 1; k <= 2; k++) {
        count_all(&t, seq, n, k);
        report(&t, k, n - k + 1);
        free(t.slots);
    }
    static const char* q[] = {"GGT", "GGTA", "GGTATT", "GGTATTTTAATT", "GGTATTTTAATTTATAGT"};
    for (int i = 0; i < 5; i++) {
        int k = (int)strlen(q[i]);
        count_all(&t, seq, n, k);
        printf("%u\t%s\n", table_get(&t, q[i], k), q[i]);
        free(t.slots);
    }
    return 0;
}
