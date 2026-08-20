'use client';

// The host. It wires two independent systems together and contributes no game
// logic of its own:
//
//   • idml — renders the view from ui/flappy.idml (parsed to flappy.config.json
//            at build time) through <ConfigProvider>/<ConfigRenderer>.
//   • id   — owns every piece of state: the bird, the pipes, the score, which
//            screen you're on, and every measurement the view lays out with.
//
// What this file actually does is only the three things a browser can do and
// id cannot: run a clock (requestAnimationFrame), listen for a key, and
// remember the best score between visits. Everything else below is a one-line
// adapter from an idml method name to an id function. There is no `if` here
// about the game -- even "is the run over?" is answered by id.

import { useEffect, useMemo, useState } from 'react';
import { ConfigProvider, ConfigRenderer } from 'idml';
import type { MethodRegistration } from 'idml';
import config from './flappy.config.json';
import { loadIdRuntime, type IdRuntime } from '../lib/id-runtime';

const BEST_KEY = 'id-flappy-best';
// The view draws three pipes: the one leaving to the left, the one the bird is
// at, and the one arriving. id decides which three those are (first_pipe).
const PIPE_SLOTS = 3;
// id is stepped in fixed 16 ms slices rather than by the raw frame delta, so
// the physics is the same whatever the display does: a slow frame runs several
// slices instead of one long one (which could carry the bird clean through a
// pipe), and a fast one runs none. MAX_CATCHUP_MS bounds how much a stalled
// tab -- a background tab gets no frames at all -- can replay on its return.
const STEP_MS = 16;
const MAX_CATCHUP_MS = 96;

export default function Page() {
  const [rt, setRt] = useState<IdRuntime | null>(null);
  const [, setFrame] = useState(0);

  // Boot: create the id state, hand it the two facts only the browser knows
  // (an entropy source for the pipe heights, and the stored best score).
  useEffect(() => {
    let alive = true;
    loadIdRuntime('/flappy.wasm').then((r) => {
      if (!alive) return;
      r.exports.init();
      r.call('seed_with', Date.now() % 65536);
      const saved = Number(window.localStorage.getItem(BEST_KEY) ?? 0);
      if (saved > 0) r.call('set_best', saved);
      setRt(r);
    });
    return () => {
      alive = false;
    };
  }, []);

  // The clock. Every frame: advance id by however many fixed slices have come
  // due, then re-render -- at which point every @value below re-reads the new
  // state. Persisting the best score is the one thing watched from out here,
  // because localStorage is the browser's, not id's.
  useEffect(() => {
    if (!rt) return;
    let raf = 0;
    let prev = performance.now();
    let owed = 0;
    let best = rt.call('best');
    const advance = (elapsed: number) => {
      owed = Math.min(owed + elapsed, MAX_CATCHUP_MS);
      while (owed >= STEP_MS) {
        rt.call('tick', STEP_MS);
        owed -= STEP_MS;
      }
      const b = rt.call('best');
      if (b !== best) {
        best = b;
        window.localStorage.setItem(BEST_KEY, String(b));
      }
      setFrame((n) => n + 1);
    };
    const loop = (now: number) => {
      advance(now - prev);
      prev = now;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    // A hidden tab is given no frames, so the game simply stops; drop the time
    // it spent away rather than replaying it the moment it comes back.
    const onShow = () => {
      prev = performance.now();
      owed = 0;
    };
    document.addEventListener('visibilitychange', onShow);
    // A handle for driving the game by hand from the console -- step it a frame
    // at a time, or read the id module directly. Development only.
    if (process.env.NODE_ENV !== 'production') {
      (window as unknown as Record<string, unknown>).idFlappy = {
        id: rt,
        step: (frames = 1) => {
          for (let i = 0; i < frames; i++) advance(STEP_MS);
        },
      };
    }
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('visibilitychange', onShow);
    };
  }, [rt]);

  // The keyboard half of the game's one input; the other half is the
  // full-screen Tap button in the .idml. Both call the same id function.
  useEffect(() => {
    if (!rt) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== 'Space' && e.code !== 'ArrowUp' && e.code !== 'Enter') return;
      e.preventDefault();
      rt.call('press');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [rt]);

  const methods = useMemo<MethodRegistration[]>(() => {
    if (!rt) return [];
    return [
      // --- geometry: id returns finished CSS percentages, so the view never
      // does arithmetic and the playfield's pixel measurements stay in id ---
      { id: 'birdTop', fn: () => rt.callStr('bird_top') },
      { id: 'birdSrc', fn: () => rt.callStr('bird_src') },
      { id: 'birdRot', fn: () => rt.callStr('bird_rot') },
      { id: 'pipeLead', fn: () => rt.callStr('pipe_lead') },
      { id: 'baseLead', fn: () => rt.callStr('base_lead') },
      { id: 'scoreW', fn: () => rt.callStr('score_w') },

      // --- rows for the two Repeats. Lists never cross the wasm boundary:
      // each row is assembled here from id's per-index accessors ---
      {
        id: 'pipes',
        fn: () =>
          Array.from({ length: PIPE_SLOTS }, (_, i) => ({
            top: rt.callStr('pipe_top', i),
          })),
      },
      {
        id: 'digits',
        fn: () =>
          Array.from({ length: rt.call('digits') }, (_, i) => ({
            src: rt.callStr('digit_src', i),
          })),
      },

      // --- scoreboard ---
      // Strings, because idml's Text renders `text || children` and a numeric
      // zero would be treated as falsy and render blank.
      { id: 'score', fn: () => String(rt.call('score')) },
      { id: 'best', fn: () => String(rt.call('best')) },
      { id: 'medalSrc', fn: () => rt.callStr('medal_src') },

      // --- which panels are up. Numbers, not strings: a visibility gate needs
      // 0 to be falsy, and every non-empty string is truthy ---
      { id: 'isReady', fn: () => rt.call('is_ready') },
      { id: 'isOver', fn: () => rt.call('is_over') },
      { id: 'showScore', fn: () => rt.call('show_score') },
      { id: 'showNew', fn: () => rt.call('show_new') },
      { id: 'flash', fn: () => rt.call('flash') },

      // --- the only handler: one press, whose meaning id decides ---
      { id: 'press', fn: () => void rt.call('press') },
    ];
  }, [rt]);

  if (!rt) return <div className="fb-boot">loading the id runtime…</div>;

  return (
    <ConfigProvider config={config} methods={methods}>
      <ConfigRenderer page="/" />
    </ConfigProvider>
  );
}
