// id-runtime — a tiny, app-agnostic bridge that lets a browser (and idml) drive
// logic written in the `id` language and compiled to WebAssembly by
// `idc.py --target wasm`.
//
// The id wasm module exports every id function plus `id_alloc` (the bump
// allocator) and its linear `memory` (see idc.py's wasm backend). id scalars
// (int) cross the JS boundary natively; id strings are NUL-terminated byte
// pointers into linear memory, which this module marshals both ways. Lists are
// never marshalled directly — the UI reads them element-by-element through id
// accessor functions, so only ints and strings ever cross.
//
// The id module is a WASI "command"-style module, so it always imports
// wasi_snapshot_preview1. We're using it as a library (no main / no real I/O),
// so those imports are satisfied with minimal stubs.

export interface IdRuntime {
  /** Raw exported id functions (call by name for full control). */
  exports: Record<string, (...args: number[]) => number>;
  /** Decode a NUL-terminated id string at `ptr` from linear memory. */
  readStr(ptr: number): string;
  /** Copy a JS string into linear memory (UTF-8 + NUL) and return its pointer. */
  writeStr(s: string): number;
  /** Call an id function, auto-marshalling string args to pointers. */
  call(name: string, ...args: (number | string)[]): number;
  /** Call an id function that returns a string; returns the decoded JS string. */
  callStr(name: string, ...args: (number | string)[]): string;
}

function makeWasiStub() {
  // None of these do anything meaningful in library use; fd_write is routed to
  // the console so a stray id print() during logic is at least visible.
  return {
    fd_write: () => 0,
    fd_read: () => 0,
    args_sizes_get: () => 0,
    args_get: () => 0,
    proc_exit: (code: number) => {
      throw new Error(`id: proc_exit(${code}) — logic tried to terminate`);
    },
  };
}

export async function loadIdRuntime(wasmUrl: string): Promise<IdRuntime> {
  const res = await fetch(wasmUrl);
  if (!res.ok) throw new Error(`id-runtime: failed to fetch ${wasmUrl} (${res.status})`);
  const bytes = await res.arrayBuffer();
  const { instance } = await WebAssembly.instantiate(bytes, {
    wasi_snapshot_preview1: makeWasiStub(),
  });
  const exports = instance.exports as unknown as {
    memory: WebAssembly.Memory;
    id_alloc: (n: number) => number;
    [k: string]: any;
  };

  const enc = new TextEncoder();
  const dec = new TextDecoder();
  // Re-read the view on every access: memory.buffer is detached and replaced
  // whenever the bump allocator grows linear memory, so a cached Uint8Array
  // would silently point at freed backing store.
  const mem = () => new Uint8Array(exports.memory.buffer);

  const readStr = (ptr: number): string => {
    const m = mem();
    let end = ptr;
    while (m[end] !== 0) end++;
    return dec.decode(m.subarray(ptr, end));
  };

  const writeStr = (s: string): number => {
    const b = enc.encode(s);
    const ptr = exports.id_alloc(b.length + 1);
    const m = mem();
    m.set(b, ptr);
    m[ptr + b.length] = 0;
    return ptr;
  };

  const marshal = (a: number | string): number =>
    typeof a === 'string' ? writeStr(a) : a;

  const call = (name: string, ...args: (number | string)[]): number => {
    const fn = exports[name];
    if (typeof fn !== 'function') {
      throw new Error(`id-runtime: no exported id function "${name}"`);
    }
    return fn(...args.map(marshal));
  };

  const callStr = (name: string, ...args: (number | string)[]): string =>
    readStr(call(name, ...args));

  return { exports, readStr, writeStr, call, callStr };
}
