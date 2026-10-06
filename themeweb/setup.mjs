// Prepare a work directory for run.mjs: the generated web files for every layer, the two bundles (the idml parser
// with the design-system guard exemption, and the React renderer), and the pages.
//
//   node setup.mjs --work DIR --bin DIR --idml DIR --pages DIR [--sys FILE] [--app FILE]
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const work = path.resolve(arg('--work', '.'));
const bin = path.resolve(arg('--bin', '.'));
const idml = path.resolve(arg('--idml', '.'));
const pagesSrc = path.resolve(arg('--pages', '.'));
const sysFile = path.resolve(arg('--sys', ''));
const appFile = path.resolve(arg('--app', ''));
const modules = process.env.IDML_NODE_MODULES || '/home/preland/git/idml/node_modules';
const esbuild = arg('--esbuild', path.join(modules, '.bin/esbuild'));
const here = path.dirname(new URL(import.meta.url).pathname);

const run = (cmd, args, opts = {}) => {
  const r = spawnSync(cmd, args, { encoding: 'utf8', timeout: 55000, ...opts });
  if (r.status !== 0) throw new Error(`${cmd} ${args.join(' ')}: exit ${r.status}\n${r.stderr}`);
  return r.stdout;
};

for (const d of ['bin', 'css', 'pages', 'web', 'native']) fs.mkdirSync(path.join(work, d), { recursive: true });
for (const b of ['themecheck', 'idtheme']) fs.copyFileSync(path.join(bin, b), path.join(work, 'bin', b));
fs.chmodSync(path.join(work, 'bin/themecheck'), 0o755);
fs.chmodSync(path.join(work, 'bin/idtheme'), 0o755);

const layers = {
  base: { css: 'base', sys: '-', app: '-' },
  sys: { css: 'sys', sys: sysFile, app: '-' },
  app: { css: 'app', sys: '-', app: appFile },
  sysapp: { css: 'sysapp', sys: sysFile, app: appFile },
};
for (const [name, l] of Object.entries(layers)) {
  const dir = path.join(work, 'css', l.css);
  fs.mkdirSync(dir, { recursive: true });
  run(path.join(work, 'bin/idtheme'), ['write', dir, l.sys, l.app]);
}
fs.writeFileSync(path.join(work, 'layers.json'), JSON.stringify(layers, null, 1));

fs.copyFileSync(path.join(work, 'css/base/idt-classes.ts'), path.join(idml, 'src/parser/idt-classes.ts'));
const env = { ...process.env, NODE_PATH: modules };
run(esbuild, [path.join(here, 'entry-parse.ts'), '--bundle', `--outfile=${path.join(work, 'web/parse.bundle.mjs')}`, '--format=esm', '--platform=node', `--alias:idml=${idml}`, '--log-level=warning'], { env });
run(esbuild, [path.join(here, 'entry-render.tsx'), '--bundle', `--outfile=${path.join(work, 'web/render.bundle.js')}`, '--format=iife', '--platform=browser', '--define:process.env.NODE_ENV="production"', `--alias:next/link=${path.join(here, 'stub-link.tsx')}`, '--jsx=automatic', `--alias:idml=${idml}`, '--log-level=warning'], { env });

const genDir = path.join(work, 'gen');
fs.rmSync(path.join(work, 'pages'), { recursive: true, force: true });
fs.mkdirSync(path.join(work, 'pages'), { recursive: true });
run(path.join(work, 'bin/themecheck'), ['gen', genDir]);
for (const [dir, skip] of [[genDir, 'gen.json'], [pagesSrc, 'pages.json']]) {
  for (const f of fs.readdirSync(dir)) if (f !== skip && /\.(idml|states)$/.test(f)) fs.copyFileSync(path.join(dir, f), path.join(work, 'pages', f));
}
const meta = [...JSON.parse(fs.readFileSync(path.join(genDir, 'gen.json'), 'utf8')), ...JSON.parse(fs.readFileSync(path.join(pagesSrc, 'pages.json'), 'utf8'))];
fs.writeFileSync(path.join(work, 'pages/pages.json'), JSON.stringify(meta));
console.log(`setup: ${Object.keys(layers).length} layers, ${meta.length} pages`);
