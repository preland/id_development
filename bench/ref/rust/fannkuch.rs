fn main() {
    let n: usize = std::env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(7);
    let mut perm = [0usize; 16];
    let mut perm1 = [0usize; 16];
    let mut count = [0usize; 16];
    let (mut maxflips, mut checksum, mut permcount) = (0i32, 0i32, 0i32);
    let mut r = n;
    for i in 0..n {
        perm1[i] = i;
    }
    loop {
        while r != 1 {
            count[r - 1] = r;
            r -= 1;
        }
        perm[..n].copy_from_slice(&perm1[..n]);
        let mut flips = 0;
        loop {
            let k = perm[0];
            if k == 0 {
                break;
            }
            let k2 = (k + 1) >> 1;
            for i in 0..k2 {
                perm.swap(i, k - i);
            }
            flips += 1;
        }
        if flips > maxflips {
            maxflips = flips;
        }
        checksum += if permcount % 2 == 0 { flips } else { -flips };
        loop {
            if r == n {
                println!("{}\nPfannkuchen({}) = {}", checksum, n, maxflips);
                return;
            }
            let p0 = perm1[0];
            for i in 0..r {
                perm1[i] = perm1[i + 1];
            }
            perm1[r] = p0;
            count[r] -= 1;
            if count[r] > 0 {
                break;
            }
            r += 1;
        }
        permcount += 1;
    }
}
