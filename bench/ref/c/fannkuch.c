#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char** argv) {
    int n = argc > 1 ? atoi(argv[1]) : 7;
    int perm[16], perm1[16], count[16];
    int maxflips = 0, checksum = 0, permcount = 0, r = n;
    for (int i = 0; i < n; i++) perm1[i] = i;
    for (;;) {
        while (r != 1) { count[r - 1] = r; r--; }
        memcpy(perm, perm1, sizeof(int) * n);
        int flips = 0, k;
        while ((k = perm[0]) != 0) {
            int k2 = (k + 1) >> 1;
            for (int i = 0; i < k2; i++) {
                int t = perm[i]; perm[i] = perm[k - i]; perm[k - i] = t;
            }
            flips++;
        }
        if (flips > maxflips) maxflips = flips;
        checksum += (permcount % 2 == 0) ? flips : -flips;
        for (;;) {
            if (r == n) {
                printf("%d\nPfannkuchen(%d) = %d\n", checksum, n, maxflips);
                return 0;
            }
            int p0 = perm1[0];
            for (int i = 0; i < r; i++) perm1[i] = perm1[i + 1];
            perm1[r] = p0;
            count[r]--;
            if (count[r] > 0) break;
            r++;
        }
        permcount++;
    }
}
