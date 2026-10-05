use std::io::Read;

const MASK: u32 = 1048575;

struct Cur<'a> {
    p: &'a [u8],
    i: usize,
}

impl<'a> Cur<'a> {
    fn peek(&self) -> u8 {
        if self.i < self.p.len() { self.p[self.i] } else { b'\n' }
    }

    fn factor(&mut self) -> u32 {
        if self.peek() == b'(' {
            self.i += 1;
            let v = self.expr();
            self.i += 1;
            return v;
        }
        let mut v: u32 = 0;
        while self.peek().is_ascii_digit() {
            v = v.wrapping_mul(10).wrapping_add((self.peek() - b'0') as u32);
            self.i += 1;
        }
        v & MASK
    }

    fn term(&mut self) -> u32 {
        let mut f = self.factor();
        while self.peek() == b'*' || self.peek() == b'/' {
            let op = self.peek();
            self.i += 1;
            let g = self.factor();
            f = if op == b'*' { f.wrapping_mul(g) & MASK } else if g == 0 { 0 } else { f / g };
        }
        f
    }

    fn expr(&mut self) -> u32 {
        let mut t = self.term();
        while self.peek() == b'+' || self.peek() == b'-' {
            let op = self.peek();
            self.i += 1;
            let u = self.term();
            t = if op == b'+' { t.wrapping_add(u) & MASK } else { t.wrapping_sub(u) & MASK };
        }
        t
    }
}

fn main() {
    let mut raw = Vec::new();
    std::io::stdin().read_to_end(&mut raw).unwrap();
    let (mut total, mut lines) = (0u32, 0u64);
    for line in raw.split(|&b| b == b'\n') {
        if line.is_empty() {
            continue;
        }
        let mut c = Cur { p: line, i: 0 };
        total = total.wrapping_add(c.expr());
        lines += 1;
    }
    println!("{}\n{}", lines, total as i32);
}
