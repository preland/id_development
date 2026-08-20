// Validate a .idml file against idml's parser (tokenizer + strict tiling rules)
// and dump the resulting UIConfig. Usage: node scripts/check-idml.mjs <file>
import { readFileSync } from 'node:fs';
import { dirname, resolve as pathResolve } from 'node:path';
import { parseIdml } from '../../../idml/src/parser/idml-parser.ts';

const file = process.argv[2];
if (!file) {
  console.error('usage: node scripts/check-idml.mjs <file.idml>');
  process.exit(2);
}
const src = readFileSync(file, 'utf8');
const baseDir = dirname(file);

try {
  const config = parseIdml(src, {
    // resolve imported .idml files relative to the entry file
    resolve: (p) => readFileSync(pathResolve(baseDir, p), 'utf8'),
  });
  console.log('OK — parsed', config.pages.length, 'page(s)');
  console.log(JSON.stringify(config, null, 2));
} catch (err) {
  console.error('PARSE ERROR:', err.message);
  process.exit(1);
}
