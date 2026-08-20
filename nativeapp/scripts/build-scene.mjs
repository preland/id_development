// Parse the native app's UI (ui/todo.idml) and resolve its percentage flex
// layout to absolute pixel geometry + a colour palette for a 640x460
// framebuffer window, writing the result to id/todo/view/layout.gen.id. The
// id renderer imports `layout()` (win_w, win_h, geo) and `palette()` (pal)
// from that file and draws directly into the software framebuffer -- no web,
// no DOM. idml owns the layout and skin; id owns state, logic and drawing.
//
// Import the parser straight from idml's source (Node strips the TS types).
// The bundled dist entry also pulls in the React/Next renderer, which can't
// resolve next/link outside a Next build -- and the parser needs none of that.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseIdml } from '../../../idml/src/parser/idml-parser.ts';

const here = dirname(fileURLToPath(import.meta.url));
const nativeapp = resolve(here, '..');
const entry = resolve(nativeapp, 'ui/todo.idml');
const out = resolve(nativeapp, 'id/todo/view/layout.gen.id');

const WIN_W = 640;
const WIN_H = 460;

const src = readFileSync(entry, 'utf8');
const config = parseIdml(src, {
  resolve: (p) => readFileSync(resolve(dirname(entry), p), 'utf8'),
});

const page = config.pages[0];
const componentsById = new Map(page.components.map((c) => [c.id, c]));

// className -> resolved pixel rect {x,y,w,h}
const rectByClass = new Map();
// className -> {bg, fg} hex strings pulled from whichever node (container
// layout node or bound component) carries the idmlStyle for that class.
const styleByClass = new Map();

function recordClass(className, idmlStyle, rect) {
  if (!className) return;
  rectByClass.set(className, rect);
  if (idmlStyle) {
    const prev = styleByClass.get(className) || {};
    styleByClass.set(className, {
      bg: idmlStyle.backgroundColor ?? prev.bg,
      fg: idmlStyle.color ?? prev.fg,
    });
  }
}

// Resolve a node into an absolute pixel rect given its parent's rect, then
// recurse into its children. Containers (Row/Col) carry className+idmlStyle
// directly on the layout node; leaf nodes instead carry a componentId that
// points into `components`, where the className+idmlStyle actually live.
function walk(node, rect) {
  const className = node.className || componentsById.get(node.componentId)?.className;
  const idmlStyle = node.idmlStyle || componentsById.get(node.componentId)?.idmlStyle;
  recordClass(className, idmlStyle, rect);

  const children = node.children || [];
  if (children.length === 0) return;

  if (node.direction === 'column') {
    // Column: children tile vertically. Cross axis (width) is 100% of the
    // parent; main axis (height) is each child's height% of the parent.
    let y = rect.y;
    for (const child of children) {
      const h = Math.round((parsePct(child.size?.height) / 100) * rect.h);
      const childRect = { x: rect.x, y, w: rect.w, h };
      walk(child, childRect);
      y += h;
    }
  } else {
    // Row: children tile horizontally. Cross axis (height) is 100% of the
    // parent; main axis (width) is each child's width% of the parent.
    let x = rect.x;
    for (const child of children) {
      const w = Math.round((parsePct(child.size?.width) / 100) * rect.w);
      const childRect = { x, y: rect.y, w, h: rect.h };
      walk(child, childRect);
      x += w;
    }
  }
}

function parsePct(s) {
  return parseFloat(String(s).replace('%', ''));
}

walk(page.layout, { x: 0, y: 0, w: WIN_W, h: WIN_H });

function need(className) {
  const rect = rectByClass.get(className);
  if (!rect) throw new Error(`build-scene: no node with className "${className}" found in ${entry}`);
  return rect;
}

const card = need('slot-card');
const input = need('slot-input');
const add = need('slot-add');
const badge = need('slot-badge');
const list = need('slot-list');
const title = need('slot-title');

// Glyphs are 8px * scale wide/tall. Vertical-center text in its box:
// ty = rect.y + (rect.h - 8*scale) / 2.
function vcenter(rect, scale) {
  return Math.round(rect.y + (rect.h - 8 * scale) / 2);
}

const titleX = title.x;
const titleY = vcenter(title, 3);

const badgeX = Math.round(badge.x + 8);
const badgeY = vcenter(badge, 2);

const inputX = Math.round(input.x + 10);
const inputY = vcenter(input, 2);

const ADD_LABEL_W = 3 * 8 * 2; // "Add" -> 3 chars * 8px * scale 2
const addX = Math.round(add.x + (add.w - ADD_LABEL_W) / 2);
const addY = vcenter(add, 2);

const geo = [
  card.x, card.y, card.w, card.h,
  input.x, input.y, input.w, input.h,
  add.x, add.y, add.w, add.h,
  badge.x, badge.y, badge.w, badge.h,
  list.x, list.y, list.w, list.h,
  titleX, titleY,
  46,
  8,
  badgeX, badgeY,
  inputX, inputY,
  addX, addY,
];

function hexToRgb(hex) {
  const m = /^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$/.exec(hex);
  if (!m) throw new Error(`build-scene: bad colour "${hex}"`);
  return [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)];
}

function styleOf(className) {
  const s = styleByClass.get(className);
  if (!s) throw new Error(`build-scene: no idmlStyle recorded for className "${className}"`);
  return s;
}

const pal = [
  hexToRgb(styleOf('slot-page').bg),      // 0 page-bg
  hexToRgb(styleOf('slot-card').bg),      // 1 card-bg
  hexToRgb(styleOf('slot-input').bg),     // 2 input-bg
  hexToRgb(styleOf('slot-add').bg),       // 3 add-bg
  hexToRgb(styleOf('slot-badge').bg),     // 4 badge-bg
  hexToRgb(styleOf('slot-title').fg),     // 5 ink (title fg)
  [148, 163, 184],                        // 6 muted (fixed default)
  hexToRgb(styleOf('slot-badgenum').fg),  // 7 accent (badge-num fg)
  [34, 197, 94],                          // 8 green (fixed default)
  [226, 232, 240],                        // 9 divider (fixed default)
];

// Group lines to mirror the semantic layout, not a flat chunk-of-4: rects get
// their own line, then the trailing scalars/points each get theirs.
const GEO_GROUPS = [4, 4, 4, 4, 4, 2, 1, 1, 2, 2, 2];
const geoLines = [];
let gi = 0;
for (const size of GEO_GROUPS) {
  gi += size;
  geoLines.push('    ' + geo.slice(gi - size, gi).join(', ') + (gi < geo.length ? ',' : ''));
}

const palLines = pal
  .map(([r, g, b], i) => `    rgb(${r}, ${g}, ${b})${i < pal.length - 1 ? ',' : ''}`)
  .join('\n');

const content = `// layout.gen.id -- resolved pixel geometry + palette for the UI. Generated by
// scripts/build-scene.mjs from ui/todo.idml (idml owns the layout, this file
// is its compiled-to-native form). Do not hand-edit -- rerun the build step.
// \`geo\` is a flat int[] of rects/points; \`pal\` is the colour palette. Index
// legend for geo:
//   0..3  card rect        4..7   input box      8..11 add button
//   12..15 badge box       16..19 list area      20,21 title text
//   22 row height  23 pad   24,25 badge text     26,27 input text
//   28,29 add label text

layout() {
  export int win_w = ${WIN_W};
  export int win_h = ${WIN_H};
  export int[] geo = [
${geoLines.join('\n')}
  ];
} return void;

palette() {
  export int[] pal = [
${palLines}
  ];
} return void;
`;

writeFileSync(out, content);
console.log(`[build:scene] wrote id/todo/view/layout.gen.id from ui/todo.idml`);
