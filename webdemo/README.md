# webdemo — a website powered by `id` + `idml`

A small to-do app that demonstrates the two halves working together:

- **`idml`** declares the entire UI (`ui/todo.idml`) — layout, styling, and which
  named methods each control binds to. It knows nothing about `id`.
- **`id`** provides **all** state and logic (`id/*.id`), compiled to
  WebAssembly. It knows nothing about the UI.

A ~110-line glue layer (`lib/id-runtime.ts` + `app/page.tsx`) is the only place
the two meet: it instantiates the id wasm module and exposes each id function as
an idml method.

```
  ui/todo.idml ──parse (build)──▶ app/todo.config.json ─┐
                                                         ├─▶ <ConfigProvider>/<ConfigRenderer>  (idml renders UI)
  id/*.id ──idc.py --target wasm─▶ public/todo.wasm ─────┘        │
                                                                  ▼
                                            method calls  ◀──  lib/id-runtime  (marshals int/string over linear memory)
```

## How the pieces connect

**State lives in id.** `id/state.id` keeps two append-only lists — `todos`
(task texts) and `toggles` (a log of toggle events). Nothing is ever mutated in
place: adding pushes, toggling pushes an event, and "is this todo done?" is the
parity of how many times its index appears in the toggle log
(`id/query.id`/`done`). This keeps the whole program inside id's one-owner-per-
global rule and 3-actions-per-block limit while still allowing arbitrary
per-item toggling.

**Logic is id functions, exposed as idml methods.** The wasm backend
(`idc.py`) exports every id function plus `id_alloc` and `memory`. `page.tsx`
wraps them as idml methods:

| idml binding        | kind    | id function(s) driven              |
| ------------------- | ------- | ---------------------------------- |
| `@remaining`        | value   | `remaining()`                      |
| `@count`            | value   | `count()`                          |
| `@todos`            | value   | `count()` + `text(i)` + `done(i)`  |
| `addTodo`           | handler | `add(string)`                      |
| `toggleItem`        | handler | `toggle(int)`                      |
| `~newtodo`          | model   | (idml form state — the input text) |

**Reactivity.** idml re-renders the page when its form-state changes, so after a
mutation the glue bumps a throwaway form cell; every `@value` method then
re-reads fresh id state. No id state is duplicated in React.

## Run it

```sh
npm install
npm run dev      # predev compiles id -> wasm and parses idml -> config
# open http://localhost:3000
```

`npm run build:id` recompiles `id/*.id` to `public/todo.wasm`;
`npm run build:config` re-parses `ui/todo.idml` to `app/todo.config.json`. Both
run automatically before `dev`/`build`.
