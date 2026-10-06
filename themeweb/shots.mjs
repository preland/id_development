import fs from 'node:fs';
import path from 'node:path';
import { readPpm, readPng, writePng } from './img.mjs';

const [outDir, dst, ...names] = process.argv.slice(2);
const TOL = 2;
fs.mkdirSync(dst, { recursive: true });
for (const name of names) {
  for (const mode of ['light', 'dark']) {
    const dir = path.join(outDir, 'base', `${name}.${mode}`);
    const nat = readPpm(fs.readFileSync(path.join(dir, 'page.ppm')));
    const web = readPng(fs.readFileSync(path.join(dir, 'web.png')));
    const diff = { w: nat.w, h: nat.h, data: new Uint8Array(nat.w * nat.h * 4) };
    let over = 0;
    for (let i = 0; i < nat.w * nat.h; i++) {
      const a = i * 4;
      const d = Math.max(Math.abs(nat.data[a] - web.data[a]), Math.abs(nat.data[a + 1] - web.data[a + 1]), Math.abs(nat.data[a + 2] - web.data[a + 2]));
      const g = 255 - Math.min(255, d * 8);
      if (d > TOL) over++;
      diff.data[a] = d > TOL ? 255 : g;
      diff.data[a + 1] = d > TOL ? 0 : g;
      diff.data[a + 2] = d > TOL ? 0 : g;
      diff.data[a + 3] = 255;
    }
    fs.writeFileSync(path.join(dst, `${name}-${mode}-native.png`), writePng(nat));
    fs.writeFileSync(path.join(dst, `${name}-${mode}-web.png`), writePng(web));
    fs.writeFileSync(path.join(dst, `${name}-${mode}-diff.png`), writePng(diff));
    console.log(`${name}.${mode} ${nat.w}x${nat.h} pixels over tolerance (unmasked, text and shadows included): ${over}`);
  }
}
