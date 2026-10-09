# idmcp

A Model Context Protocol server in pure id: JSON-RPC 2.0 over stdio, one JSON
object per line. The goal (later milestones) is that an agent changes id code
only through tools that keep it valid. This milestone (M0 to M2) has the wire
layer, the `echo` tool and the read-only project tools (below).

Build: `idc/bin/idc idmcp -o idmcp/bin/idmcp` (every inline case runs in the build).

Layout: `main.id` (line loop), `conf.id` (constants), `wire/` (JSON replies,
escaping, request reading and type checks), `server/` (method dispatch, tools/call),
`tool/` (the project tools, M2), `sample/` (a tiny library the tests open).
stdout carries protocol lines only.

## M0 spikes (measured, warm compiler cache, one core, this machine)

| What | Result |
| --- | --- |
| `idc <small project> --check --diagnostics=json` (spikes/small, 2 functions, 4 cases) | 3.4 s wall (1.5 s user) |
| same on idmcp itself (43 functions, 218 cases) | 3.3 s wall |
| cases-running build `idc spikes/small -o bin`, one case edited | 5.5 s wall |
| same build, nothing changed | 0.9 s wall |
| build with a red case (spikes/redcase) | 5.6 s wall, exit 1, `file:line: test failed: f(args) = got, expected want` |
| full idmcp build, nothing changed | 1.2 s wall |
| `input()` on a 100000-byte line | returns **1023** bytes (3000000-byte line: 1023 too); the rest of the line is lost |
| `wire_fill` (per-byte `stdio_read_some_mem`) on a 200000-byte request, echoed back | correct, 0.18 s |
| `wire_fill` on a 17000000-byte line | answers -32600 "Request too large", next request still served; 12.8 s (one read per byte), so the 16 MiB limit is a ceiling, not a target |

Diagnostics stream (`--diagnostics=json`): they go to **stderr**, stdout stays
empty; one JSON object per line, each with `kind`. Two lines from a project with
a seeded error (`spikes/bad`: an unknown function and a type mismatch), values
trimmed:

    {"kind":"diagnostic","severity":"error","code":"E0304","file":"spikes/bad/main.id","line":4,"column":15,"end_column":31,"function":"main","message":"no such function 'missing_function'","why":"a call names a function this program defines, a builtin, ...","fixes":[{"description":"check the spelling of 'missing_function', or define it as a function; ..."}],...}
    {"kind":"diagnostic","severity":"error","code":null,"file":"spikes/bad/main.id","line":5,"column":null,"end_column":null,"function":"main","message":"cannot initialize string 'text' with a int value","why":"","fixes":[],"related":[],"follows":null,"rendered":"error: cannot initialize string 'text' with a int value\n  --> spikes/bad/main.id:5\n  in main\n  |\n5 |   string text = argc;"}

The stream ends with `{"kind":"summary","errors":2,"codes":["E0304"]}` (on stderr
too). Exit status 1. Note the second diagnostic has `code: null` and
`column: null`: not every diagnostic is coded or positioned. A passing
`--check` prints `ok: PROJECT (N functions, M cases)` and exits 0.

## Wire layer

- `wire_quote(text)` writes a JSON string literal: `"` `\` as `\"` `\\`, newline,
  tab, carriage return as `\n` `\t` `\r`, every other control byte 1..31 as
  `\u00XX`, everything else (UTF-8 included) as bytes.
- `wire_unescape(raw)` undoes every escape in the bytes between a string's quotes,
  `\uXXXX` included (scalar values only: a surrogate half and `\u0000` stay as
  written). `wire_string(doc, pos)` reads the string at a `json_find` position.
- `wire_kind(doc, pos)` names the value there: `string object array boolean null
  number invalid`, or `missing` for position -1. `wire_expect(doc, path, "a,b")`
  checks a member's kind against a list.
- `wire_check(line)`: 0 for a dispatchable request, -32700 for a line that is not
  one complete JSON object (`wire_balanced`: brackets and strings, no key or
  value checking, brackets are counted not matched), -32600 for an object that
  is not a JSON-RPC 2.0 request (`jsonrpc` must be the string `"2.0"`, `method` a
  string, `id` absent, string or number, `params` absent, object or array).
- `wire_result`, `wire_failure`, `wire_id` build replies; the id is passed as JSON
  text so a number stays a number.
- `wire_fill(buffer, cap)` reads one line into a buffer the caller allocated; -1
  at end of input, -2 too long (consumed), -3 holds a NUL.

## Decisions to review

- `initialize` echoes the client's `params.protocolVersion` when it is a string,
  else answers `2025-06-18` (conf.id). A real version negotiation is not done.
- A valid request without `id` is a notification and gets no reply, whatever its
  method (so an unknown notification is silent, as JSON-RPC requires).
- `{x}` (balanced, not JSON) is answered -32600, not -32700: the structural
  check does not look at keys or values. A line that is not even bracket-balanced,
  e.g. `{bad`, is -32700.
- `ping` is not implemented (not in the milestone); it answers -32601.
- Blank lines are ignored.

## idstd gaps worked around

- `input()` truncates at 1023 bytes: replaced by `wire_fill` over
  `stdio_read_some_mem` (one syscall-level read per byte).
- No JSON string encoder: `str_quote` escapes non-ASCII as `\u{...}`, which is not
  JSON. `wire_quote` is the replacement (a candidate for idstd `core/fmt/json`).
- `json_text` does not decode `\uXXXX`, and it undoes `\\` first, so an escaped
  backslash followed by `u0041` cannot be told from `A`; `wire_string`
  reads the raw token instead.
- No validation in the reader: malformed input gives wrong answers. `wire_balanced`
  is a structural stand-in only.
- A test case's `stdin "..."` cannot contain a NUL (it is cut there), so the NUL
  path of `wire_fill` is covered through `wire_clean` on a poked buffer, not
  end to end.
- Counted scaling constraints (`[time:O(n)]`) cannot be put on `wire_fill`: they
  need two cases whose argument sizes differ, and its size is the stdin, not an
  argument.

## M2: read-only project tools (`tool/`)

Every tool answers one text content block holding compact JSON with `ok`, `error`
and the payload; a refusal is `{"ok":false,"error":CODE,"message":...}` inside a
normal result (not `isError`). Codes: `no_project`, `outside_project`,
`not_found`, `bad_argument`, `workspace_failed`, `compiler_unavailable`,
`too_large`. A session has one project: `project_open` copies it into a private
workspace under `$TMPDIR` (`fs_mktemp`) and every other tool works on the copy;
the root and workspace live in the process environment (`IDMCP_ROOT`,
`IDMCP_WORK`, cleared when the server starts). `IDMCP_IDC` names the compiler
driver (default: the umbrella's `idc/bin/idc`, `tool_program_default` in conf.id).

| Tool | Arguments | Answer |
| --- | --- | --- |
| `project_open` | `path` | `project{name,files,functions,cases,untested}`, `tree` (top two levels), `baseline{errors,codes}` |
| `list` | `path`, `depth` (1 to 4) | `entries` (dirs, and files with their functions: name, line, cases) or, for a file, `functions` |
| `read` | `name` [+ `std`] or `file` [+ `line`, `count` <= 200] | function: file, line, signature, doc sentence, text with cases, `callers`/`callees` (<= 10 each, with totals); file: a numbered slice |
| `find` | `query`, `where` (`project`, `std`, or both) | <= 10 matches: exact name first, then project, then public idstd rows; signature, file, line, doc sentence |
| `calls` | `name`, `direction` (`callers`, `callees`, both), `depth` (1 to 3) | edges (from, from_at, to, to_at, kind), <= 100 per direction |
| `explain` | `code` (E and four digits) | `idc --explain` text |
| `check` | none | `errors` and <= 10 diagnostics: code, file, line, function, message, help, edits (the compiler's first fix) |

Scope: a path with a `..` segment, or one that `fs_realpath` resolves (symlinks
followed) outside the workspace root, is `outside_project`. Names sent to the
compiler (`--where`, `--explain`) must be letters, digits, `_` or `:` (`tool_safe`),
since arguments are passed one per line and a newline could add an option.

Commands run through `exec_run` with a 55 s limit (`tool_time_limit`), stdout
and stderr merged. Cases run with the project directory as the working directory,
so the tests find the compiler at `../idc/bin/idc` and the sample at `sample/`.

### Findings and workarounds

- `exec_run` drains a pipe 4 KB per 10 ms poll. `idc --calls` prints the whole
  standard library (15000 rows, 3.6 MB): through a pipe that is 13 to 18 s. The call
  graph is therefore written to a file by `sh -c 'exec "$1" "$2" --calls > "$3"'`
  (arguments, not interpolation) and cut down to the rows that touch the project
  (`tool_project_rows`). A fix belongs in idstd (read stdout without waiting on
  stderr); then `tool_snapshot` can use `tool_idc` again.
- Neighbours of an idstd function (`read` with `std`, `calls` on a library name)
  are the project's callers only: library-internal edges are dropped at open time.
- idc's cache is keyed by path, so the first `--calls` and `--check` of a fresh
  workspace are cold: `project_open` of the 3-function sample takes about 8 s, of
  which the two idc runs are nearly all. A big project will take longer; each run
  is capped at 55 s.
- The sample is inside this tree, so idc compiles it with idmcp: it has no
  `main` (a library) and unique names (`sample_*`).
- A function with a doc comment separated by a blank line has no doc: the span
  starts at the comment block directly above the signature.
- Old workspaces are never deleted (a reopen starts a new one): removing a
  directory named by an environment variable is not done on trust.
