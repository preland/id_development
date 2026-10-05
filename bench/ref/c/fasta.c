#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define IM 139968
#define IA 3877
#define IC 29573

typedef struct { char c; double p; } Amino;

static int last = 42;

static double gen_random(double max) {
    last = (last * IA + IC) % IM;
    return max * last / IM;
}

static const char* ALU =
    "GGCCGGGCGCGGTGGCTCACGCCTGTAATCCCAGCACTTTGGGAGGCCGAGGCGGGCGGATCACCTGAGGTCAGGAGTTCGAGACCAGCC"
    "TGGCCAACATGGTGAAACCCCGTCTCTACTAAAAATACAAAAATTAGCCGGGCGTGGTGGCGCGCGCCTGTAATCCCAGCTACTCGGGAGG"
    "CTGAGGCAGGAGAATCGCTTGAACCCGGGAGGCGGAGGTTGCAGTGAGCCGAGATCGCGCCACTGCACTCCAGCCTGGGCGACAGAGCGAGA"
    "CTCCGTCTCAAAAA";

static Amino iub[] = {
    {'a', 0.27}, {'c', 0.12}, {'g', 0.12}, {'t', 0.27}, {'B', 0.02}, {'D', 0.02}, {'H', 0.02}, {'K', 0.02},
    {'M', 0.02}, {'N', 0.02}, {'R', 0.02}, {'S', 0.02}, {'V', 0.02}, {'W', 0.02}, {'Y', 0.02},
};
static Amino homosapiens[] = {
    {'a', 0.3029549426680}, {'c', 0.1979883004921}, {'g', 0.1975473066391}, {'t', 0.3015094502008},
};

static void make_cumulative(Amino* a, int n) {
    double p = 0.0;
    for (int i = 0; i < n; i++) { p += a[i].p; a[i].p = p; }
}

static void make_repeat(const char* id, const char* desc, int n) {
    printf(">%s %s\n", id, desc);
    int len = (int)strlen(ALU);
    char line[61];
    int k = 0;
    while (n > 0) {
        int m = n < 60 ? n : 60;
        for (int i = 0; i < m; i++) { line[i] = ALU[k]; k++; if (k == len) k = 0; }
        line[m] = 0;
        puts(line);
        n -= m;
    }
}

static void make_random(const char* id, const char* desc, Amino* a, int an, int n) {
    printf(">%s %s\n", id, desc);
    char line[61];
    while (n > 0) {
        int m = n < 60 ? n : 60;
        for (int i = 0; i < m; i++) {
            double r = gen_random(1.0);
            int j = 0;
            while (a[j].p < r) j++;
            line[i] = a[j].c;
        }
        line[m] = 0;
        puts(line);
        n -= m;
    }
    (void)an;
}

int main(int argc, char** argv) {
    int n = argc > 1 ? atoi(argv[1]) : 1000;
    make_cumulative(iub, 15);
    make_cumulative(homosapiens, 4);
    make_repeat("ONE", "Homo sapiens alu", n * 2);
    make_random("TWO", "IUB ambiguity codes", iub, 15, n * 3);
    make_random("THREE", "Homo sapiens frequency", homosapiens, 4, n * 5);
    return 0;
}
