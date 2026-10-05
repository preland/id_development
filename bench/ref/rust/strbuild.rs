fn main() {
    let n: usize = std::env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(1000);
    let mut buf = String::new();
    let mut s: u32 = 777;
    for i in 0..n {
        s = s.wrapping_mul(1103515245).wrapping_add(12345) & 0x7fffffff;
        if i > 0 {
            buf.push(',');
        }
        buf.push_str(&(s % 100000).to_string());
    }
    let (mut count, mut maxlen, mut sum) = (0i32, 0usize, 0u32);
    for tok in buf.split(',') {
        let mut v: u32 = 0;
        for b in tok.bytes() {
            v = v.wrapping_mul(10).wrapping_add((b - b'0') as u32);
        }
        sum = sum.wrapping_add(v);
        maxlen = maxlen.max(tok.len());
        count += 1;
    }
    println!("{}\n{}\n{}\n{}", buf.len(), count, sum as i32, maxlen);
}
