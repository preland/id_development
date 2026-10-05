#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { char* key; int len; int count; int64_t total; } Slot;

static uint32_t hash_bytes(const char* p, int n) {
    uint32_t h = 2166136261u;
    for (int i = 0; i < n; i++) { h ^= (unsigned char)p[i]; h *= 16777619u; }
    return h;
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
    size_t tcap = 1024, used = 0;
    Slot* t = calloc(tcap, sizeof(Slot));
    long rows = 0;
    int64_t grand = 0;
    size_t i = 0;
    while (i < len && buf[i] != '\n') i++;
    i++;
    while (i < len) {
        size_t line_end = i;
        while (line_end < len && buf[line_end] != '\n') line_end++;
        size_t f0 = i;
        while (buf[f0] != ',') f0++;
        size_t k0 = f0 + 1;
        size_t k1 = k0;
        while (buf[k1] != ',') k1++;
        size_t q0 = k1 + 1;
        size_t q1 = q0;
        int qty = 0;
        while (buf[q1] != ',') { qty = qty * 10 + (buf[q1] - '0'); q1++; }
        int price = 0;
        for (size_t p = q1 + 1; p < line_end; p++) price = price * 10 + (buf[p] - '0');
        int64_t amount = (int64_t)qty * price;
        if (used * 2 >= tcap) {
            Slot* old = t;
            size_t oc = tcap;
            tcap *= 2;
            t = calloc(tcap, sizeof(Slot));
            for (size_t a = 0; a < oc; a++) {
                if (old[a].key) {
                    size_t h = hash_bytes(old[a].key, old[a].len) & (tcap - 1);
                    while (t[h].key) h = (h + 1) & (tcap - 1);
                    t[h] = old[a];
                }
            }
            free(old);
        }
        int klen = (int)(k1 - k0);
        size_t h = hash_bytes(buf + k0, klen) & (tcap - 1);
        for (;;) {
            if (!t[h].key) {
                t[h].key = malloc(klen);
                memcpy(t[h].key, buf + k0, klen);
                t[h].len = klen;
                t[h].count = 1;
                t[h].total = amount;
                used++;
                break;
            }
            if (t[h].len == klen && memcmp(t[h].key, buf + k0, klen) == 0) {
                t[h].count++;
                t[h].total += amount;
                break;
            }
            h = (h + 1) & (tcap - 1);
        }
        rows++;
        grand += amount;
        i = line_end + 1;
    }
    int64_t maxtotal = 0;
    long busy = 0;
    for (size_t a = 0; a < tcap; a++) {
        if (t[a].key) {
            if (t[a].total > maxtotal) maxtotal = t[a].total;
            if (t[a].count >= 10) busy++;
        }
    }
    printf("%ld\n%ld\n%lld\n%lld\n%ld\n", rows, (long)used, (long long)grand, (long long)maxtotal, busy);
    return 0;
}
