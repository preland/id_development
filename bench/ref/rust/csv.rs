use std::collections::HashMap;
use std::io::Read;

fn main() {
    let mut raw = String::new();
    std::io::stdin().read_to_string(&mut raw).unwrap();
    let mut m: HashMap<&str, (u32, i64)> = HashMap::new();
    let (mut rows, mut grand) = (0u64, 0i64);
    for line in raw.lines().skip(1) {
        let mut f = line.split(',');
        let _id = f.next().unwrap();
        let cust = f.next().unwrap();
        let qty: i64 = f.next().unwrap().parse().unwrap();
        let price: i64 = f.next().unwrap().parse().unwrap();
        let amount = qty * price;
        let e = m.entry(cust).or_insert((0, 0));
        e.0 += 1;
        e.1 += amount;
        rows += 1;
        grand += amount;
    }
    let mut maxtotal = 0i64;
    let mut busy = 0u64;
    for (_, (c, t)) in m.iter() {
        if *t > maxtotal {
            maxtotal = *t;
        }
        if *c >= 10 {
            busy += 1;
        }
    }
    println!("{}\n{}\n{}\n{}\n{}", rows, m.len(), grand, maxtotal, busy);
}
