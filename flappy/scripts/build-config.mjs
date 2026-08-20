// Parse the idml UI (ui/flappy.idml) into a validated UIConfig the app imports
// at build time, so no .idml parser ships to the browser.
//
// The parser is imported from idml's source rather than its bundle: the bundle
// entry also pulls in the React/Next renderer, whose next/link import can't
// resolve outside a Next build, and the parser needs none of that.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseIdml } from '../../../idml/src/parser/idml-parser.ts';

const here = dirname(fileURLToPath(import.meta.url));
const app = resolve(here, '..');
const entry = resolve(app, 'ui/flappy.idml');
const out = resolve(app, 'app/flappy.config.json');

const config = parseIdml(readFileSync(entry, 'utf8'), {
  resolve: (p) => readFileSync(resolve(dirname(entry), p), 'utf8'),
});

writeFileSync(out, JSON.stringify(config, null, 2) + '\n');
const n = config.pages[0].components.length;
console.log(`[build:config] wrote app/flappy.config.json (${n} components)`);
