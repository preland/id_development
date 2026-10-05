fn merge(src: &[i32], dst: &mut [i32], lo: usize, mid: usize, hi: usize) {
    let (mut i, mut j, mut k) = (lo, mid, lo);
    while i < mid && j < hi {
        if src[j] < src[i] {
            dst[k] = src[j];
            j += 1;
        } else {
            dst[k] = src[i];
            i += 1;
        }
        k += 1;
    }
    while i < mid {
        dst[k] = src[i];
        i += 1;
        k += 1;
    }
    while j < hi {
        dst[k] = src[j];
        j += 1;
        k += 1;
    }
}

fn main() {
    let n: usize = std::env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(1000);
    let mut a = vec![0i32; n];
    let mut b = vec![0i32; n];
    let mut s: u32 = 12345;
    for x in a.iter_mut() {
        s = s.wrapping_mul(1103515245).wrapping_add(12345) & 0x7fffffff;
        *x = s as i32;
    }
    let mut w = 1;
    let mut flip = false;
    while w < n {
        let (src, dst) = if flip { (&b, &mut a) } else { (&a, &mut b) };
        let mut lo = 0;
        while lo < n {
            let mid = (lo + w).min(n);
            let hi = (lo + 2 * w).min(n);
            merge(src, dst, lo, mid, hi);
            lo += 2 * w;
        }
        flip = !flip;
        w *= 2;
    }
    let r = if flip { &b } else { &a };
    let mut sum: u32 = 0;
    for (i, v) in r.iter().enumerate() {
        sum = sum.wrapping_add((*v as u32).wrapping_mul((i + 1) as u32));
    }
    println!("{}\n{}\n{}\n{}", sum as i32, r[0], r[n / 2], r[n - 1]);
}
