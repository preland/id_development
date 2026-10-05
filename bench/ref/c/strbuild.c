#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char** argv) {
    int n = argc > 1 ? atoi(argv[1]) : 1000;
    size_t cap = 1024, len = 0;
    char* buf = malloc(cap);
    uint32_t s = 777;
    for (int i = 0; i < n; i++) {
        s = (s * 1103515245u + 12345u) & 0x7fffffffu;
        char tok[16];
        int m = snprintf(tok, sizeof tok, "%u", s % 100000u);
        if (len + m + 2 > cap) { while (len + m + 2 > cap) cap *= 2; buf = realloc(buf, cap); }
        if (i > 0) buf[len++] = ',';
        memcpy(buf + len, tok, m);
        len += m;
    }
    int count = 0, maxlen = 0;
    uint32_t sum = 0;
    size_t i = 0;
    while (i <= len) {
        size_t j = i;
        uint32_t v = 0;
        while (j < len && buf[j] != ',') { v = v * 10 + (uint32_t)(buf[j] - '0'); j++; }
        sum += v;
        if ((int)(j - i) > maxlen) maxlen = (int)(j - i);
        count++;
        i = j + 1;
    }
    printf("%d\n%d\n%d\n%d\n", (int)len, count, (int)sum, maxlen);
    free(buf);
    return 0;
}
