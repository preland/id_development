// Parse the idml UI (ui/todo.idml) into a validated UIConfig JSON that the app
// imports at build time (app/todo.config.json). Keeping the parse at build time
// means no .idml parser ships to the browser — the app loads a plain config.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
// Import the parser straight from idml's source (Node strips the TS types). The
// bundled dist entry also pulls in the React/Next renderer, which can't resolve
// next/link outside a Next build — and the parser needs none of that.
import { parseIdml } from '../../../idml/src/parser/idml-parser.ts';

const here = dirname(fileURLToPath(import.meta.url));
const webdemo = resolve(here, '..');
const entry = resolve(webdemo, 'ui/todo.idml');
const out = resolve(webdemo, 'app/todo.config.json');

const src = readFileSync(entry, 'utf8');
const config = parseIdml(src, {
  resolve: (p) => readFileSync(resolve(dirname(entry), p), 'utf8'),
});

writeFileSync(out, JSON.stringify(config, null, 2) + '\n');
console.log(`[build:config] wrote app/todo.config.json (${config.pages.length} page)`);
