import { px } from './img.mjs';

export const TOL = 2;

export function compareComputed(nat, web) {
  let bad = 0;
  const details = [];
  nat.forEach((r, i) => {
    const w = web[i];
    if (!w || w.n !== r.n || w.prop !== r.prop || w.value !== r.value) {
      bad++;
      if (details.length < 12) details.push({ node: r.n, prop: r.prop, native: r.value, web: w ? w.value : null });
    }
  });
  return { rows: nat.length, bad, details };
}

export function compareRects(nat, web) {
  let exact = 0, within1 = 0, max = 0;
  const details = [];
  nat.forEach((r, i) => {
    const w = web[i];
    const d = w ? [r[1] - w[0], r[2] - w[1], r[3] - w[2], r[4] - w[3]].map(Math.abs) : [1e9, 1e9, 1e9, 1e9];
    const m = Math.max(...d);
    max = Math.max(max, m);
    if (m <= 0.02) exact++;
    if (m <= 1.0) within1++;
    else if (details.length < 12) details.push({ node: r[0], native: r.slice(1, 5), web: w });
  });
  return { nodes: nat.length, exact, within1, max, details };
}

export function compareText(nat, web) {
  let same = 0;
  const details = [];
  nat.forEach((r, i) => {
    if (web[i] && web[i].n === r.n && web[i].lines === r.lines) same++;
    else if (details.length < 12) details.push({ node: r.n, native: r.lines, web: web[i] ? web[i].lines : null });
  });
  return { rows: nat.length, same, details };
}

const byNode = (computed) => {
  const m = new Map();
  for (const r of computed) {
    if (!m.has(r.n)) m.set(r.n, {});
    m.get(r.n)[r.prop] = r.value;
  }
  return m;
};
const hex = (s) => (s && s.startsWith('#') ? parseInt(s.slice(1), 16) : null);
const len = (s) => (s && s.endsWith('px') ? parseFloat(s) : 0);
const inside = (a, b) => a[1] >= b[1] && a[2] >= b[2] && a[1] + a[3] <= b[1] + b[3] && a[2] + a[4] <= b[2] + b[4];

export function probes(nat, web) {
  const props = byNode(nat.computed);
  let total = 0, eqWeb = 0, eqExpN = 0, eqExpW = 0, withExp = 0;
  const details = [];
  const R = nat.rects.map((r) => [r[0], r[1], r[2], r[3], r[4]]);
  const halos = nat.rects.filter((r) => (props.get(r[0]) || {})['box-shadow'] && props.get(r[0])['box-shadow'] !== 'none').map((r) => {
    const v = props.get(r[0])['box-shadow'].split(' ').map(Number);
    const g = v[6] + Math.abs(v[5]) + 4;
    return [r[1] - g, r[2] - g, r[3] + 2 * g, r[4] + 2 * g, r[1], r[2], r[3], r[4]];
  });
  const add = (node, name, x, y, expected) => {
    if (x < 0 || y < 0 || x >= nat.ppm.w || y >= nat.ppm.h) return;
    if (halos.some((h) => x >= h[0] && y >= h[1] && x < h[0] + h[2] && y < h[1] + h[3] && !(x >= h[4] && y >= h[5] && x < h[4] + h[6] && y < h[5] + h[7]))) return;
    const a = px(nat.ppm, x, y), b = px(web.png, x, y);
    total++;
    if (a === b) eqWeb++;
    else if (details.length < 12) details.push({ node, probe: name, x, y, native: a.toString(16), web: b.toString(16) });
    if (expected != null) {
      withExp++;
      if (a === expected) eqExpN++;
      if (b === expected) eqExpW++;
    }
  };
  const textual = new Set(nat.text.map((t) => t.n));
  R.forEach((r, i) => {
    const [, x, y, w, h] = r;
    const p = props.get(r[0]) || {};
    const leaf = i === R.length - 1 || !inside(R[i + 1], r);
    const bg = hex(p['background-color']);
    const rad = Math.min(len(p['border-radius']), Math.floor(Math.min(w, h) / 2));
    const bw = len(p['border-width']);
    if (bg != null && leaf && w >= 4 && h >= 4) {
      if (textual.has(r[0])) add(r[0], 'corner-free', x + w - 3 - rad, y + h - 3 - rad, bg);
      else add(r[0], 'centre', x + Math.floor(w / 2), y + Math.floor(h / 2), bg);
      if (rad > 0) {
        const k = Math.floor(rad * 0.5 + 1);
        if (k < w / 2 && k < h / 2) {
          if (!textual.has(r[0])) add(r[0], 'corner-in', x + k, y + k, bg);
          add(r[0], 'corner-in-br', x + w - 1 - k, y + h - 1 - k, bg);
        }
        if (rad * 0.414 >= 2.5) add(r[0], 'corner-out', x, y, null);
      }
    }
    if (bw > 0 && leaf && w >= 8 && h >= 8) {
      const bc = hex(p['border-color']);
      add(r[0], 'border-top', x + Math.floor(w / 2), y + Math.floor(bw / 2), bc);
      add(r[0], 'border-left', x + Math.floor(bw / 2), y + Math.floor(h / 2), bc);
    }
  });
  return { total, native_eq_web: eqWeb, with_expected: withExp, native_eq_exp: eqExpN, web_eq_exp: eqExpW, details };
}

export function maskedDiff(nat, web) {
  const { w, h } = nat.ppm;
  if (web.png.w !== w || web.png.h !== h) return { counted: 0, bad: w * h, tol: TOL, masked: 0, details: [{ size: [web.png.w, web.png.h] }] };
  const mask = new Uint8Array(w * h);
  const props = byNode(nat.computed);
  const mark = (x, y, ww, hh, g) => {
    for (let j = Math.max(0, Math.floor(y - g)); j < Math.min(h, Math.ceil(y + hh + g)); j++)
      for (let i = Math.max(0, Math.floor(x - g)); i < Math.min(w, Math.ceil(x + ww + g)); i++) mask[j * w + i] = 1;
  };
  for (const t of nat.text) {
    const r = nat.rects[t.n];
    const lh = len((props.get(r[0]) || {})['line-height']) || 0;
    mark(r[1], r[2], r[3], Math.max(r[4], t.lines * lh), 2);
  }
  for (const r of nat.rects) {
    const p = props.get(r[0]) || {};
    const sh = p['box-shadow'];
    if (sh && sh !== 'none') {
      const v = sh.split(' ').map(Number);
      mark(r[1], r[2], r[3], r[4], v[6] + Math.abs(v[5]) + 4);
    }
    const rad = Math.min(len(p['border-radius']), Math.floor(Math.min(r[3], r[4]) / 2));
    if (rad > 0) {
      const g = rad + 3;
      mark(r[1], r[2], g, g, 0);
      mark(r[1] + r[3] - g, r[2], g, g, 0);
      mark(r[1], r[2] + r[4] - g, g, g, 0);
      mark(r[1] + r[3] - g, r[2] + r[4] - g, g, g, 0);
    }
  }
  let counted = 0, bad = 0, masked = 0;
  const details = [];
  for (let j = 0; j < h; j++) {
    for (let i = 0; i < w; i++) {
      if (mask[j * w + i]) { masked++; continue; }
      counted++;
      const a = (j * w + i) * 4;
      const d = Math.max(Math.abs(nat.ppm.data[a] - web.png.data[a]), Math.abs(nat.ppm.data[a + 1] - web.png.data[a + 1]), Math.abs(nat.ppm.data[a + 2] - web.png.data[a + 2]));
      if (d > TOL) { bad++; if (details.length < 8) details.push({ x: i, y: j, native: px(nat.ppm, i, j).toString(16), web: px(web.png, i, j).toString(16) }); }
    }
  }
  return { counted, bad, tol: TOL, masked, details };
}

const INK = 48;
const TEXT_TOL = 3;

function inkBox(img, x0, y0, w, h) {
  const seen = new Map();
  for (let j = Math.max(0, y0); j < Math.min(img.h, y0 + h); j += 3) for (let i = Math.max(0, x0); i < Math.min(img.w, x0 + w); i += 3) { const k = px(img, i, j); seen.set(k, (seen.get(k) || 0) + 1); }
  let bgp = 0, top = -1;
  for (const [k, n] of seen) if (n > top) { top = n; bgp = k; }
  const br = (bgp >> 16) & 255, bgr = (bgp >> 8) & 255, bb = bgp & 255;
  let minx = 1e9, miny = 1e9, maxx = -1, maxy = -1;
  for (let j = Math.max(0, y0); j < Math.min(img.h, y0 + h); j++) {
    for (let i = Math.max(0, x0); i < Math.min(img.w, x0 + w); i++) {
      const a = (j * img.w + i) * 4;
      if (Math.max(Math.abs(img.data[a] - br), Math.abs(img.data[a + 1] - bgr), Math.abs(img.data[a + 2] - bb)) > INK) {
        if (i < minx) minx = i;
        if (i > maxx) maxx = i;
        if (j < miny) miny = j;
        if (j > maxy) maxy = j;
      }
    }
  }
  return maxx < 0 ? null : [minx, miny, maxx, maxy];
}

export function inkBoxes(nat, web) {
  const props = byNode(nat.computed);
  let nodes = 0, agree = 0;
  const details = [];
  for (const t of nat.text) {
    const r = nat.rects[t.n];
    const lh = len((props.get(r[0]) || {})['line-height']) || 0;
    const hh = Math.max(r[4], t.lines * lh);
    const a = inkBox(nat.ppm, r[1], r[2], r[3], hh);
    const b = inkBox(web.png, r[1], r[2], r[3], hh);
    nodes++;
    const ok = a && b && a.every((v, k) => Math.abs(v - b[k]) <= TEXT_TOL);
    if (ok) agree++;
    else if (details.length < 8) details.push({ node: t.n, native: a, web: b });
  }
  return { nodes, agree, tol: TEXT_TOL, details };
}
