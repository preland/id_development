use std::io::{BufWriter, Write};

const IM: i32 = 139968;
const IA: i32 = 3877;
const IC: i32 = 29573;

const ALU: &[u8] = b"GGCCGGGCGCGGTGGCTCACGCCTGTAATCCCAGCACTTTGGGAGGCCGAGGCGGGCGGATCACCTGAGGTCAGGAGTTCGAGACCAGCCTGGCCAACATGGTGAAACCCCGTCTCTACTAAAAATACAAAAATTAGCCGGGCGTGGTGGCGCGCGCCTGTAATCCCAGCTACTCGGGAGGCTGAGGCAGGAGAATCGCTTGAACCCGGGAGGCGGAGGTTGCAGTGAGCCGAGATCGCGCCACTGCACTCCAGCCTGGGCGACAGAGCGAGACTCCGTCTCAAAAA";

struct Rng {
    last: i32,
}

impl Rng {
    fn next(&mut self, max: f64) -> f64 {
        self.last = (self.last * IA + IC) % IM;
        max * (self.last as f64) / (IM as f64)
    }
}

fn cumulative(a: &[(u8, f64)]) -> Vec<(u8, f64)> {
    let mut p = 0.0;
    a.iter()
        .map(|&(c, q)| {
            p += q;
            (c, p)
        })
        .collect()
}

fn make_repeat<W: Write>(out: &mut W, id: &str, desc: &str, mut n: usize) {
    writeln!(out, ">{} {}", id, desc).unwrap();
    let mut k = 0;
    let mut line = [0u8; 61];
    while n > 0 {
        let m = n.min(60);
        for i in 0..m {
            line[i] = ALU[k];
            k += 1;
            if k == ALU.len() {
                k = 0;
            }
        }
        line[m] = b'\n';
        out.write_all(&line[..m + 1]).unwrap();
        n -= m;
    }
}

fn make_random<W: Write>(out: &mut W, rng: &mut Rng, id: &str, desc: &str, a: &[(u8, f64)], mut n: usize) {
    writeln!(out, ">{} {}", id, desc).unwrap();
    let mut line = [0u8; 61];
    while n > 0 {
        let m = n.min(60);
        for i in 0..m {
            let r = rng.next(1.0);
            let mut j = 0;
            while a[j].1 < r {
                j += 1;
            }
            line[i] = a[j].0;
        }
        line[m] = b'\n';
        out.write_all(&line[..m + 1]).unwrap();
        n -= m;
    }
}

fn main() {
    let n: usize = std::env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(1000);
    let iub = cumulative(&[
        (b'a', 0.27), (b'c', 0.12), (b'g', 0.12), (b't', 0.27), (b'B', 0.02), (b'D', 0.02), (b'H', 0.02), (b'K', 0.02),
        (b'M', 0.02), (b'N', 0.02), (b'R', 0.02), (b'S', 0.02), (b'V', 0.02), (b'W', 0.02), (b'Y', 0.02),
    ]);
    let homo = cumulative(&[(b'a', 0.3029549426680), (b'c', 0.1979883004921), (b'g', 0.1975473066391), (b't', 0.3015094502008)]);
    let stdout = std::io::stdout();
    let mut out = BufWriter::with_capacity(1 << 16, stdout.lock());
    let mut rng = Rng { last: 42 };
    make_repeat(&mut out, "ONE", "Homo sapiens alu", n * 2);
    make_random(&mut out, &mut rng, "TWO", "IUB ambiguity codes", &iub, n * 3);
    make_random(&mut out, &mut rng, "THREE", "Homo sapiens frequency", &homo, n * 5);
}
