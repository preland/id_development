struct Node {
    kids: Option<Box<(Node, Node)>>,
}

fn make(d: i32) -> Node {
    if d > 0 {
        Node { kids: Some(Box::new((make(d - 1), make(d - 1)))) }
    } else {
        Node { kids: None }
    }
}

fn check(n: &Node) -> i32 {
    match &n.kids {
        None => 1,
        Some(k) => 1 + check(&k.0) + check(&k.1),
    }
}

fn main() {
    let mut maxd: i32 = std::env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(10);
    let mind = 4;
    if maxd < mind + 2 {
        maxd = mind + 2;
    }
    let stretch = maxd + 1;
    let s = make(stretch);
    println!("stretch tree of depth {}\t check: {}", stretch, check(&s));
    drop(s);
    let longlived = make(maxd);
    let mut d = mind;
    while d <= maxd {
        let iters = 1 << (maxd - d + mind);
        let mut sum = 0;
        for _ in 0..iters {
            let t = make(d);
            sum += check(&t);
        }
        println!("{}\t trees of depth {}\t check: {}", iters, d, sum);
        d += 2;
    }
    println!("long lived tree of depth {}\t check: {}", maxd, check(&longlived));
}
