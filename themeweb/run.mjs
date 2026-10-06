// The render check: the native gui kit and the web (React idml in headless Chromium) render the same pages, and what
// each says about them is compared, level by level.
//
//   node run.mjs --work DIR [--pages NAME,NAME] [--layers base,sys,app] [--modes light,dark] [--out DIR]
//
// DIR holds what setup.mjs made: pages/, bin/ (themecheck, idtheme), web/ (the two bundles) and css/<layer>/idt.css.
// Every number it prints is a count of rows, nodes or pixels that agree, with the tolerance each level uses.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { readPpm, readPng, px } from './img.mjs';
import { compareRects, compareComputed, compareText, probes, maskedDiff, inkBoxes } from './cmp.mjs';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const work = path.resolve(arg('--work', '.'));
const only = arg('--pages', '') ? arg('--pages', '').split(',') : null;
const layersWanted = arg('--layers', 'base').split(',');
const modesWanted = arg('--modes', 'light,dark').split(',');
const outDir = path.resolve(arg('--out', path.join(work, 'out')));
const range = arg('--range', '');
const idmlRoot = arg('--idml', '');
const quiet = process.argv.includes('--quiet');

const modules = process.env.IDML_NODE_MODULES || '/home/preland/git/idml/node_modules';
const require = createRequire(modules + '/');
const puppeteer = require(modules + '/puppeteer-core');
const parserMod = await import(path.join(work, 'web/parse.bundle.mjs'));
const bundle = fs.readFileSync(path.join(work, 'web/render.bundle.js'), 'utf8');
const pages = JSON.parse(fs.readFileSync(path.join(work, 'pages/pages.json'), 'utf8'));
const layers = JSON.parse(fs.readFileSync(path.join(work, 'layers.json'), 'utf8'));

const normColor = (v) => {
  const m = v.match(/rgba?\(([^)]+)\)/);
  if (!m) return v;
  const a = m[1].split(',').map((x) => x.trim());
  const [r, g, b] = a.map(Number);
  const al = a.length > 3 ? Number(a[3]) : 1;
  if (al !== 1) return `rgba(${a.join(',')})`;
  return '#' + [r, g, b].map((x) => x.toString(16).padStart(2, '0')).join('');
};
export const normValue = (prop, v) => {
  if (/color$/.test(prop)) return normColor(v);
  if (prop === 'box-shadow') {
    if (v === 'none') return v;
    const nums = (v.match(/-?\d*\.?\d+/g) || []).map(Number);
    if (v.startsWith('rgb(')) nums.splice(3, 0, 1);
    return nums.join(' ');
  }
  if (prop === 'transition-duration') return Math.round(parseFloat(v) * (v.endsWith('ms') ? 1 : 1000)) + 'ms';
  return v;
};

const readLines = (f) => fs.readFileSync(f, 'utf8').split('\n').filter(Boolean);

function native(page, mode, layer, w, h, dir) {
  const args = ['render', path.join(work, 'pages', page + '.idml'), mode, String(w), String(h), dir, layers[layer].sys || '-', layers[layer].app || '-'];
  const t0 = Date.now();
  const r = spawnSync(path.join(work, 'bin/themecheck'), args, { encoding: 'utf8', timeout: 50000, cwd: path.join(work, 'native') });
  if (r.status !== 0) throw new Error(`themecheck ${page} ${mode} ${layer}: exit ${r.status} ${r.stderr}`);
  return {
    ms: Date.now() - t0,
    rects: readLines(path.join(dir, 'rects.txt')).map((l) => l.split(' ').map(Number)),
    computed: readLines(path.join(dir, 'computed.txt')).map((l) => { const [n, prop, ...v] = l.split('|'); return { n: +n, prop, value: v.join('|') }; }),
    text: readLines(path.join(dir, 'text.txt')).map((l) => { const [n, c] = l.split('|'); return { n: +n, lines: +c }; }),
    ppm: readPpm(fs.readFileSync(path.join(dir, 'page.ppm'))),
  };
}

async function web(browser, page, mode, layer, w, h, nat, dir) {
  const src = path.join(work, 'pages', page + '.idml');
  const config = parserMod.parseIdml(fs.readFileSync(src, 'utf8'), { resolve: (p) => fs.readFileSync(path.resolve(path.dirname(src), p), 'utf8') });
  config.tokens = JSON.parse(fs.readFileSync(path.join(work, 'css', layers[layer].css, 'idt.tokens.json'), 'utf8'));
  const css = fs.readFileSync(path.join(work, 'css', layers[layer].css, 'idt.css'), 'utf8');
  const pg = await browser.newPage();
  await pg.setViewport({ width: w, height: h, deviceScaleFactor: 1 });
  const errors = [];
  pg.on('pageerror', (e) => errors.push(String(e)));
  pg.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await pg.setContent(`<!doctype html><html class="${mode}"><head><meta charset="utf-8"><style>html,body{margin:0;padding:0}*{outline:none !important}</style><style>${css}</style></head><body><div id="app" class="idt" style="width:${w}px;height:${h}px"></div></body></html>`);
  await pg.addScriptTag({ content: bundle });
  await pg.evaluate((c, d) => window.__mount(c, d), config, mode === 'dark');
  await pg.waitForFunction('window.__mounted === true', { timeout: 20000 });
  const kinds = nat.rects.map((r) => r[5]);
  const tag = await pg.evaluate((ks) => {
    const nodes = [...document.querySelectorAll('[data-idml-node]')].slice(1);
    if (nodes.length !== ks.length) return { error: `${nodes.length} elements in the page, ${ks.length} nodes in the tape` };
    nodes.forEach((n, i) => {
      const el = ks[i] === 1 || ks[i] === 2 ? n : n.firstElementChild || n;
      el.setAttribute('data-sty', String(i));
      n.setAttribute('data-nd', String(i));
    });
    return { ok: true };
  }, kinds);
  if (tag.error) throw new Error(`${page} ${mode} ${layer}: ${tag.error}`);
  const states = fs.existsSync(src + '.states') ? readLines(src + '.states').map((l) => l.split(' ').map(Number)) : [];
  if (states.length) {
    const c = await pg.createCDPSession();
    await c.send('DOM.enable');
    await c.send('CSS.enable');
    const { root } = await c.send('DOM.getDocument', { depth: -1 });
    for (const [ord, mask] of states) {
      const { nodeId } = await c.send('DOM.querySelector', { nodeId: root.nodeId, selector: `[data-sty="${ord}"]` });
      const forced = [];
      if (mask & 1) forced.push('hover');
      if (mask & 2) forced.push('focus-visible');
      if (mask & 4) forced.push('active');
      if (forced.length) await c.send('CSS.forcePseudoState', { nodeId, forcedPseudoClasses: forced });
      if (mask & 8) await pg.evaluate((i) => { document.querySelector(`[data-sty="${i}"]`).disabled = true; }, ord);
    }
  }
  await pg.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
  const wanted = nat.computed.map((r) => [r.n, r.prop]);
  const textNodes = nat.text.map((r) => r.n);
  const got = await pg.evaluate((pairs, tn) => {
    const rects = [...document.querySelectorAll('[data-nd]')].map((n) => { const b = n.getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; });
    const el = (i) => document.querySelector(`[data-sty="${i}"]`);
    const values = pairs.map(([i, p]) => getComputedStyle(el(i)).getPropertyValue(p));
    const lines = tn.map((i) => {
      const r = document.createRange();
      r.selectNodeContents(el(i));
      const tops = new Set([...r.getClientRects()].filter((q) => q.width > 0).map((q) => Math.round(q.top)));
      return tops.size;
    });
    return { rects, values, lines };
  }, wanted, textNodes);
  const png = await pg.screenshot({ type: 'png' });
  fs.writeFileSync(path.join(dir, "web.png"), png);
  await pg.close();
  return {
    errors,
    rects: got.rects,
    computed: wanted.map(([n, p], i) => ({ n, prop: p, value: normValue(p, got.values[i]) })),
    text: textNodes.map((n, i) => ({ n, lines: got.lines[i] })),
    png: readPng(Buffer.from(png)),
  };
}

const results = [];
const browser = await puppeteer.launch({
  executablePath: arg('--chromium', '/etc/profiles/per-user/preland/bin/chromium'),
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--force-color-profile=srgb', '--font-render-hinting=none', '--disable-lcd-text', '--force-device-scale-factor=1', '--hide-scrollbars', `--user-data-dir=${path.join(work, 'chrome-profile')}`],
});
let list = pages.filter((p) => !only || only.includes(p.name));
if (range) { const [a, b] = range.split('..').map(Number); list = list.slice(a, b); }
for (const layer of layersWanted) {
  for (const p of list) {
    if (p.layers && !p.layers.includes(layer)) continue;
    for (const mode of modesWanted) {
      const dir = path.join(outDir, layer, `${p.name}.${mode}`);
      fs.mkdirSync(dir, { recursive: true });
      const nat = native(p.name, mode, layer, p.w, p.h, dir);
      const wb = await web(browser, p.name, mode, layer, p.w, p.h, nat, dir);
      const l1 = compareComputed(nat.computed, wb.computed);
      const l2 = compareRects(nat.rects, wb.rects);
      const lt = compareText(nat.text, wb.text);
      const l3 = probes(nat, wb);
      const l3d = maskedDiff(nat, wb);
      const l4 = inkBoxes(nat, wb);
      const r = { page: p.name, mode, layer, nodes: nat.rects.length, l1, l2, text: lt, l3, l3diff: l3d, ink: l4, nativeMs: nat.ms, errors: wb.errors };
      results.push(r);
      if (!quiet) console.log(`${layer}/${p.name}.${mode}: nodes=${r.nodes} L1 ${l1.rows - l1.bad}/${l1.rows} L2 exact ${l2.exact}/${l2.nodes} within1 ${l2.within1}/${l2.nodes} max ${l2.max.toFixed(2)} text ${lt.same}/${lt.rows} L3 probes ${l3.native_eq_web}/${l3.total} (exp native ${l3.native_eq_exp} web ${l3.web_eq_exp}) diff ${l3d.bad}/${l3d.counted} ink ${l4.agree}/${l4.nodes}`);
    }
  }
}
await browser.close();
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, `report-${layersWanted.join('+')}-${Date.now()}.json`), JSON.stringify(results, null, 1));
const sum = (f) => results.reduce((a, r) => a + f(r), 0);
console.log(`SUMMARY runs=${results.length} nodes=${sum((r) => r.nodes)}`);
console.log(`L1 computed: rows=${sum((r) => r.l1.rows)} mismatches=${sum((r) => r.l1.bad)}`);
console.log(`L2 geometry: nodes=${sum((r) => r.l2.nodes)} exact=${sum((r) => r.l2.exact)} within1=${sum((r) => r.l2.within1)} over1=${sum((r) => r.l2.nodes - r.l2.within1)} max=${Math.max(0, ...results.map((r) => r.l2.max)).toFixed(2)}`);
console.log(`text lines: rows=${sum((r) => r.text.rows)} same=${sum((r) => r.text.same)}`);
console.log(`L3 probes: total=${sum((r) => r.l3.total)} native==web=${sum((r) => r.l3.native_eq_web)} native==expected=${sum((r) => r.l3.native_eq_exp)} web==expected=${sum((r) => r.l3.web_eq_exp)}`);
console.log(`L3 masked diff: counted=${sum((r) => r.l3diff.counted)} differing=${sum((r) => r.l3diff.bad)} (tolerance ${results[0] ? results[0].l3diff.tol : 0} per channel)`);
console.log(`text ink boxes: nodes=${sum((r) => r.ink.nodes)} agree=${sum((r) => r.ink.agree)} (within ${results[0] ? results[0].ink.tol : 0} px per edge)`);
console.log(`page errors: ${sum((r) => r.errors.length)}`);
process.exitCode = sum((r) => r.l1.bad) + sum((r) => r.l2.nodes - r.l2.within1) + sum((r) => r.l3.total - r.l3.native_eq_web) + sum((r) => r.l3diff.bad) + sum((r) => r.ink.nodes - r.ink.agree) > 0 ? 1 : 0;
