#include <stdio.h>
#include <stdlib.h>

int main(int argc, char** argv) {
    int n = argc > 1 ? atoi(argv[1]) : 200;
    int inside = 0, total = 0;
    for (int y = 0; y < n; y++) {
        double ci = 2.0 * y / n - 1.0;
        for (int x = 0; x < n; x++) {
            double cr = 2.0 * x / n - 1.5;
            double zr = 0.0, zi = 0.0;
            int i = 0;
            while (i < 50 && zr * zr + zi * zi <= 4.0) {
                double t = zr * zr - zi * zi + cr;
                zi = 2.0 * zr * zi + ci;
                zr = t;
                i++;
            }
            total += i;
            if (i == 50) inside++;
        }
    }
    printf("%d\n%d\n", inside, total);
    return 0;
}
