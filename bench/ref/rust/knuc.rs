use std::collections::HashMap;
use std::io::Read;

fn count_all(seq: &[u8], k: usize) -> HashMap<&[u8], u32> {
    let mut m: HashMap<&[u8], u32> = HashMap::new();
    if seq.len() >= k {
        for i in 0..=(seq.len() - k) {
            *m.entry(&seq[i..i + k]).or_insert(0) += 1;
        }
    }
    m
}

fn report(m: &HashMap<&[u8], u32>, total: u64) {
    let mut v: Vec<(&[u8], u32)> = m.iter().map(|(k, c)| (*k, *c)).collect();
    v.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));
    for (k, c) in v {
        let pct = (c as u64) * 100000 / total;
        println!("{} {}.{:03}", String::from_utf8_lossy(k), pct / 1000, pct % 1000);
    }
    println!();
}

fn main() {
    let mut raw = Vec::new();
    std::io::stdin().read_to_end(&mut raw).unwrap();
    let seq: Vec<u8> = raw.into_iter().filter(|&b| b != b'\n').collect();
    for k in 1..=2usize {
        let m = count_all(&seq, k);
        report(&m, (seq.len() - k + 1) as u64);
    }
    for q in ["GGT", "GGTA", "GGTATT", "GGTATTTTAATT", "GGTATTTTAATTTATAGT"] {
        let m = count_all(&seq, q.len());
        println!("{}\t{}", m.get(q.as_bytes()).copied().unwrap_or(0), q);
    }
}
