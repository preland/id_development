#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static void merge(const int32_t* src, int32_t* dst, int lo, int mid, int hi) {
    int i = lo, j = mid, k = lo;
    while (i < mid && j < hi) {
        if (src[j] < src[i]) dst[k++] = src[j++];
        else dst[k++] = src[i++];
    }
    while (i < mid) dst[k++] = src[i++];
    while (j < hi) dst[k++] = src[j++];
}

int main(int argc, char** argv) {
    int n = argc > 1 ? atoi(argv[1]) : 1000;
    int32_t* a = malloc(sizeof(int32_t) * n);
    int32_t* b = malloc(sizeof(int32_t) * n);
    uint32_t s = 12345;
    for (int i = 0; i < n; i++) {
        s = (s * 1103515245u + 12345u) & 0x7fffffffu;
        a[i] = (int32_t)s;
    }
    int32_t* src = a;
    int32_t* dst = b;
    for (int w = 1; w < n; w *= 2) {
        for (int lo = 0; lo < n; lo += 2 * w) {
            int mid = lo + w < n ? lo + w : n;
            int hi = lo + 2 * w < n ? lo + 2 * w : n;
            merge(src, dst, lo, mid, hi);
        }
        int32_t* t = src; src = dst; dst = t;
    }
    uint32_t sum = 0;
    for (int i = 0; i < n; i++) sum += (uint32_t)src[i] * (uint32_t)(i + 1);
    printf("%d\n%d\n%d\n%d\n", (int)sum, src[0], src[n / 2], src[n - 1]);
    free(a); free(b);
    return 0;
}
