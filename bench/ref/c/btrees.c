#include <stdio.h>
#include <stdlib.h>

typedef struct Node { struct Node *left, *right; } Node;

static Node* make(int d) {
    Node* n = malloc(sizeof(Node));
    if (d > 0) { n->left = make(d - 1); n->right = make(d - 1); }
    else { n->left = NULL; n->right = NULL; }
    return n;
}

static int check(const Node* n) {
    if (!n->left) return 1;
    return 1 + check(n->left) + check(n->right);
}

static void drop(Node* n) {
    if (n->left) { drop(n->left); drop(n->right); }
    free(n);
}

int main(int argc, char** argv) {
    int maxd = argc > 1 ? atoi(argv[1]) : 10;
    int mind = 4;
    if (maxd < mind + 2) maxd = mind + 2;
    int stretch = maxd + 1;
    Node* s = make(stretch);
    printf("stretch tree of depth %d\t check: %d\n", stretch, check(s));
    drop(s);
    Node* longlived = make(maxd);
    for (int d = mind; d <= maxd; d += 2) {
        int iters = 1 << (maxd - d + mind);
        int sum = 0;
        for (int i = 0; i < iters; i++) {
            Node* t = make(d);
            sum += check(t);
            drop(t);
        }
        printf("%d\t trees of depth %d\t check: %d\n", iters, d, sum);
    }
    printf("long lived tree of depth %d\t check: %d\n", maxd, check(longlived));
    drop(longlived);
    return 0;
}
