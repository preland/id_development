fn main() {
    let n: i32 = std::env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(200);
    let (mut inside, mut total) = (0i32, 0i32);
    for y in 0..n {
        let ci = 2.0 * (y as f64) / (n as f64) - 1.0;
        for x in 0..n {
            let cr = 2.0 * (x as f64) / (n as f64) - 1.5;
            let (mut zr, mut zi) = (0.0f64, 0.0f64);
            let mut i = 0;
            while i < 50 && zr * zr + zi * zi <= 4.0 {
                let t = zr * zr - zi * zi + cr;
                zi = 2.0 * zr * zi + ci;
                zr = t;
                i += 1;
            }
            total += i;
            if i == 50 {
                inside += 1;
            }
        }
    }
    println!("{}\n{}", inside, total);
}
