use std::io::Read;

enum Json {
    Null,
    False,
    True,
    Num(i32),
    Str(usize),
    Arr(Vec<Json>),
    Obj(Vec<(usize, Json)>),
}

struct P<'a> {
    b: &'a [u8],
    i: usize,
}

impl<'a> P<'a> {
    fn ws(&mut self) {
        while self.i < self.b.len() && matches!(self.b[self.i], b' ' | b'\n' | b'\r' | b'\t') {
            self.i += 1;
        }
    }

    fn string(&mut self) -> usize {
        self.i += 1;
        let start = self.i;
        while self.b[self.i] != b'"' {
            if self.b[self.i] == b'\\' {
                self.i += 1;
            }
            self.i += 1;
        }
        let len = self.i - start;
        self.i += 1;
        len
    }

    fn value(&mut self) -> Json {
        match self.b[self.i] {
            b'{' => {
                self.i += 1;
                self.ws();
                let mut kids = Vec::new();
                if self.b[self.i] == b'}' {
                    self.i += 1;
                    return Json::Obj(kids);
                }
                loop {
                    self.ws();
                    let k = self.string();
                    self.ws();
                    self.i += 1;
                    self.ws();
                    let v = self.value();
                    kids.push((k, v));
                    self.ws();
                    let c = self.b[self.i];
                    self.i += 1;
                    if c == b'}' {
                        return Json::Obj(kids);
                    }
                }
            }
            b'[' => {
                self.i += 1;
                self.ws();
                let mut kids = Vec::new();
                if self.b[self.i] == b']' {
                    self.i += 1;
                    return Json::Arr(kids);
                }
                loop {
                    self.ws();
                    kids.push(self.value());
                    self.ws();
                    let c = self.b[self.i];
                    self.i += 1;
                    if c == b']' {
                        return Json::Arr(kids);
                    }
                }
            }
            b'"' => Json::Str(self.string()),
            b't' => {
                self.i += 4;
                Json::True
            }
            b'f' => {
                self.i += 5;
                Json::False
            }
            b'n' => {
                self.i += 4;
                Json::Null
            }
            c => {
                let neg = c == b'-';
                if neg {
                    self.i += 1;
                }
                let mut v: u32 = 0;
                while self.i < self.b.len() && self.b[self.i].is_ascii_digit() {
                    v = v.wrapping_mul(10).wrapping_add((self.b[self.i] - b'0') as u32);
                    self.i += 1;
                }
                Json::Num(if neg { 0u32.wrapping_sub(v) as i32 } else { v as i32 })
            }
        }
    }
}

#[derive(Default)]
struct Stats {
    values: u64,
    numsum: u32,
    strbytes: u64,
    keybytes: u64,
    trues: u64,
    maxdepth: u32,
}

fn walk(j: &Json, depth: u32, st: &mut Stats) {
    st.values += 1;
    if depth > st.maxdepth {
        st.maxdepth = depth;
    }
    match j {
        Json::Num(n) => st.numsum = st.numsum.wrapping_add(*n as u32),
        Json::Str(n) => st.strbytes += *n as u64,
        Json::True => st.trues += 1,
        Json::Arr(k) => {
            for c in k {
                walk(c, depth + 1, st);
            }
        }
        Json::Obj(k) => {
            for (kl, c) in k {
                st.keybytes += *kl as u64;
                walk(c, depth + 1, st);
            }
        }
        Json::Null | Json::False => {}
    }
}

fn main() {
    let mut raw = Vec::new();
    std::io::stdin().read_to_end(&mut raw).unwrap();
    let mut p = P { b: &raw, i: 0 };
    p.ws();
    let root = p.value();
    p.ws();
    assert_eq!(p.i, raw.len());
    let mut st = Stats::default();
    walk(&root, 1, &mut st);
    println!("{}\n{}\n{}\n{}\n{}\n{}", st.values, st.numsum as i32, st.strbytes, st.keybytes, st.trues, st.maxdepth);
}
