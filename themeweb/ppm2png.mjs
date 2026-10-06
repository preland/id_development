import fs from 'node:fs';
import { readPpm, writePng } from './img.mjs';
const [src, dst] = process.argv.slice(2);
fs.writeFileSync(dst, writePng(readPpm(fs.readFileSync(src))));
