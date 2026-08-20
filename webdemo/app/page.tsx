'use client';

// The demo host. This file wires two independent systems together:
//   • idml  — renders the UI from ui/todo.idml (parsed to todo.config.json at
//             build time) via <ConfigProvider>/<ConfigRenderer>.
//   • id    — supplies ALL state and logic, compiled to public/todo.wasm and
//             driven through lib/id-runtime.
// Not a single line of app logic lives here: every method below is a thin
// adapter that calls an id function. idml never knows it's talking to id, and
// id never knows it's driving a React UI.

import { useEffect, useMemo, useState } from 'react';
import { ConfigProvider, ConfigRenderer } from 'idml';
import type { MethodRegistration } from 'idml';
import config from './todo.config.json';
import { loadIdRuntime, type IdRuntime } from '../lib/id-runtime';

interface Helpers {
  set: (name: string, value: unknown) => void;
  item?: { index: number; text: string; done: boolean };
}

export default function Page() {
  const [rt, setRt] = useState<IdRuntime | null>(null);

  useEffect(() => {
    let alive = true;
    loadIdRuntime('/todo.wasm').then((r) => {
      r.exports.init(); // create the id-side state (empty lists) exactly once
      if (alive) setRt(r);
    });
    return () => {
      alive = false;
    };
  }, []);

  const methods = useMemo<MethodRegistration[]>(() => {
    if (!rt) return [];
    // idml re-renders the whole page when page form-state changes, at which
    // point every @value method below re-reads fresh id state. So after a
    // mutation we bump a throwaway form cell to trigger that re-render.
    let rev = 0;
    const bump = (set: Helpers['set']) => set('$rev', ++rev);

    return [
      // --- reactive values the UI binds with @ ---
      // Return strings: idml's Text renders `text || children`, so a numeric 0
      // would be treated as falsy and render blank. "0" is truthy.
      { id: 'count', fn: () => String(rt.call('count')) },
      { id: 'remaining', fn: () => String(rt.call('remaining')) },
      // Numeric predicate for visibility gates (`?@hasTodos` / `?!@hasTodos`).
      // count/remaining return strings so a "0" renders in the UI, but "0" is
      // truthy — visibility needs a real number (0 == empty == falsy).
      { id: 'hasTodos', fn: () => rt.call('count') },
      {
        id: 'todos',
        fn: () => {
          // Build the row array purely from id scalar accessors — no id list
          // ever crosses the wasm boundary.
          const n = rt.call('count');
          const rows = [];
          for (let i = 0; i < n; i++) {
            rows.push({
              index: i,
              text: rt.callStr('text', i),
              done: rt.call('done', i) === 1,
            });
          }
          return rows;
        },
      },
      // --- handlers the UI binds by bare name ---
      {
        id: 'addTodo',
        fn: (values: Record<string, unknown>, helpers: Helpers) => {
          const text = String(values?.newtodo ?? '').trim();
          if (!text) return;
          rt.call('add', text); // JS string → linear memory → id todos list
          helpers.set('newtodo', ''); // clear the input
          bump(helpers.set);
        },
      },
      {
        id: 'toggleItem',
        fn: (_values: Record<string, unknown>, helpers: Helpers) => {
          if (!helpers.item) return;
          rt.call('toggle', helpers.item.index);
          bump(helpers.set);
        },
      },
    ];
  }, [rt]);

  if (!rt) {
    return (
      <div style={{ padding: '2rem', fontFamily: 'system-ui', color: '#64748b' }}>
        loading the id runtime…
      </div>
    );
  }

  return (
    <ConfigProvider config={config} methods={methods}>
      <ConfigRenderer page="/" />
    </ConfigProvider>
  );
}
