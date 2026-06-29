# id language — VS Code extension

Syntax highlighting and linting for the `id` language (compiled by `idc.py`).

- **Coloring** — a TextMate grammar for comments, keywords (`if else while
  return`, `export import`), types (`int float string void`), the builtins
  (`print input read_all len charat chr to_int push pop put flush getkey
  sleep_ms ticks`), strings with escapes, numbers, function names, and
  operators.
- **Linting** — runs `idc.py` in the background and turns its
  `file:line: error|warning: …` output into editor diagnostics (red/yellow
  squiggles), updating as you type.

## Install (from source)

This extension isn't published to the Marketplace. To run it:

```sh
# open the extension folder in VS Code and press F5 ("Run Extension"),
# or install it into your editor:
cd editors/vscode-id
npx @vscode/vsce package        # produces id-lang-0.1.0.vsix
code --install-extension id-lang-0.1.0.vsix
```

Open any `.id` file and you get coloring immediately; linting starts once
`idc.py` is found.

## How linting finds `idc.py`

By default the extension searches upward from the edited file for a file named
`idc.py` (so it just works inside this repo). Override it with the `id.idcPath`
setting. It lints by invoking `idc.py <target> --emit-c <tempfile>`, which runs
the full front end and semantic checks (action limit, function-per-file limit,
name/type consistency, export/import access, type checking) but stops before
calling the C compiler.

Because `idc` halts at the first error, linting surfaces one error at a time
(plus any warnings); fix it and the next appears.

## Settings

| Setting | Default | Meaning |
| --- | --- | --- |
| `id.idcPath` | `""` | Path to `idc.py`. Empty = search upward from the file. |
| `id.pythonPath` | `python3` | Interpreter used to run `idc.py`. |
| `id.lint.scope` | `directory` | `directory` compiles the file's whole folder as one program (catches cross-file and import errors, matching how `id` programs are built); `file` compiles just the open file. |
| `id.lint.run` | `onType` | `onType`, `onSave`, or `off`. |
| `id.lint.debounce` | `400` | Milliseconds idle before linting while typing. |

Command: **id: Lint now** re-runs the linter on demand.

## Notes

- `id` programs are usually a directory of files compiled together, so the
  default `directory` scope is the most accurate. Switch to `file` scope for
  stand-alone snippets if cross-file references produce false positives.
