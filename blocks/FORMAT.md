# The `.blk` format and the `blocks` tool

`blocks` is a Scratch-like block-coding tool written in `id`. It is a text format
for programs, a checker for the rules, a VM that runs them, a command line, and
a block editor (a window, and a headless replay of it) that edits the text.

The scope is Scratch's; the rules are `id`'s. Where they disagree `id` wins and
the Scratch interface is only the way to look at it: every variable has one
declared type, a conversion is a block you place, "when green flag clicked" *is*
`main`, and every other script and custom block is a function that obeys the
function rules (three actions to a block, two levels of nesting, three
functions to a page, two different test cases each, no two functions with the
same logic). The rules are checked on the text, so a future block editor cannot
build what the checker refuses.

```
idc/bin/idc blocks -o blocks.bin            # build (the project is the directory)
blocks.bin run   FILE.blk [--frames N]      # run the green flag, print what was said and the final state
blocks.bin check FILE.blk                   # rule violations, each with id's error code; exit 1 if any
blocks.bin test  FILE.blk                   # run every function's cases in the VM; exit 1 if any fails
blocks.bin edit  FILE.blk                   # the block editor, in a window (see "The editor")
blocks.bin edit  FILE.blk --script S.txt [--dump] [--boxes] [--render-after OUT.ppm]   # the same, headless
blocks.bin render FILE.blk OUT.ppm [--size W H]   # the picture of the editor on the file, as a PPM
blocks.bin export FILE.blk OUTDIR         # write the program as an id project under OUTDIR (see "Export to id")
```

## The file

Line based. A line is blank, a `// comment` line, or one of the lines below.
Indentation is two spaces per level and only function bodies are indented.

```
sprite NAME                                  a sprite's page; what follows belongs to it
var TYPE NAME [= VALUE]                      a variable or list of the sprite
fn NAME(TYPE a, TYPE b) return TYPE [on "message"]
  BODY LINES                                 indented one level
CASE LINES                                   at column 0, directly under the function
```

`TYPE` is `int`, `float`, `string`, or one of those followed by `[]` (a list); a
function that returns nothing says `return void`. The stage and each sprite
are pages; a variable is global to the program but is declared on a page, and
names are unique program-wide (below). Every function belongs to the page
above it.

`main` is the green flag and must be exactly
`fn main(int argc, string[] argv) return int` (it is called with 1 and
`["blocks"]`). A function with `on "message"` and no parameters is a script
that runs when that message is broadcast (a "when I receive" hat); it must
return void.

### Statements

One per line; the first word says which.

| line | meaning |
| --- | --- |
| `TYPE NAME = EXPR` | declare a local, visible to the end of its block |
| `NAME = EXPR` | set a local or variable |
| `NAME[INDEX] = EXPR` | set an element of a list |
| `NAME(ARGS)` | call a function or a builtin, dropping the result |
| `if EXPR` / `else` | the block below (one level deeper) runs if EXPR is not 0; `else` is at the `if`'s indent |
| `while EXPR` | repeat the block below while EXPR is not 0 (`forever` is `while 1`) |
| `break` | leave the innermost `while` |
| `return` / `return EXPR` | leave the function; the last body line of a function that returns a value is its `return` |

There is no `repeat N`, `else if`, or `chain`: a loop that counts is a `while`
with a counter, and a body that needs a fourth action becomes two functions.

### Expressions

Literals: `42`, `2.5`, `"text"` (escapes `\n`, `\"`, `\\`), and `[a, b, c]` for a
list where a list type is expected (a declaration, a parameter, a `var`).
Names, `NAME[INDEX]`, `FN(ARGS)`, parentheses, prefix `-` and `!`, and the binary
operators `|| && == != < > <= >= + - * / %` with `id`'s precedence. Operands of
an operator have the **same type**: `1 + 2.5` is an error; write
`int_to_float(1) + 2.5`. `+` joins two strings; `%` is for ints. `&&` and `||`
stop at the left operand when it decides. A condition is an int.

### Builtin blocks

| block | type | does |
| --- | --- | --- |
| `say(s)` | string | the sprite says s (a line `Sprite: s` in the output) |
| `move(n)` `turn(deg)` `point(deg)` `goto(x, y)` | float | motion; direction 90 is right, 0 is up |
| `show()` `hide()` | | looks |
| `xpos()` `ypos()` `direction()` | float | the sprite's position and direction |
| `wait(secs)` | float | sleep (the machine's clock runs 33 ms a frame) |
| `broadcast(msg)` | string | start every script `on msg` |
| `len(x)` | string or list | length |
| `push(xs, v)` `pop(xs)` `insert(xs, i, v)` `delete(xs, i)` | list | list blocks; `pop` answers the last element |
| `str_sub(s, i, n)` `charat(s, i)` `str_find(s, t)` | string | as in `id` (`charat` is -1 past the end, `str_find` -1 when absent) |
| `int_to_float` `float_to_int` `int_to_str` `float_to_str` `str_to_int` `str_to_float` | | the conversion blocks; `float_to_int` truncates toward zero |

Sensing, sound, clones, pen, keys and mouse are not in this milestone.

## Test cases

A case is a line at column 0 under the function it tests, in `id`'s case syntax:

```
(ARGS):(EXPECTED)
given NAME = VALUE ... (ARGS):(EXPECTED) then NAME:(VALUE) ...
```

`ARGS` are literals, one per parameter, `EXPECTED` is the return value (empty,
`()`, for `return void`). `given NAME = VALUE` sets a variable before the
call and `then NAME:(VALUE)` reads one after it; they are how a function that
works on state is tested. Every case runs on a fresh machine with the variables at
their declared initial values, so cases cannot see one another. Two cases of
one function must differ (spacing does not count). An expected list or float is
compared as `id` prints it (six significant digits).

## The rules and their codes

`blocks check` reports every violation as `FILE:LINE: error: MESSAGE [CODE]`
with the code `idc` uses for the same mistake (`idc --explain CODE`).

| code | rule here |
| --- | --- |
| E0101 / E0102 | a token that is missing / not allowed; also an indent that is not two spaces |
| E0201 | more than 3 actions in a block: each statement, `if`, `else`, `while` is one, `return` and `break` none |
| E0202 | an `if` or `while` nested more than two levels (the body itself is level one) |
| E0203 | more than 3 functions on a sprite's page |
| E0301 / E0302 | undefined variable / a local declared twice in a function |
| E0303 | one name, two types, across the whole program: variables, parameters and locals together |
| E0304 | no such function |
| E0401 | two functions with one name; or a function named like a builtin block |
| E0402 | two functions with the same signature and logic, up to the names of parameters and locals |
| E0407 | the same, up to the values of literals: the value should be a parameter |
| E0501 | fewer than 2 cases |
| E0502 | a case repeats an earlier one |
| E0503 / E0505 | a case with the wrong number of arguments / the wrong expected value for the return type |
| E0602 | `return` of the wrong type, or no `return` at the end of a function that returns a value |
| E0604 | an operator on operand types it does not take |
| E0606 | an argument or an assigned value of the wrong type; also a malformed `main` |

Assigning or initializing with the wrong type is E0606: `idc` reports it
without a code. Run-time errors (division by zero, a list index outside the
list, `pop` of an empty list, `str_sub` outside the string, calls nested more
than 32 deep) stop the script, are printed as `error: ... in Sprite`, and make
`blocks run` exit 1.

## The machine

A program is compiled to a table of five-cell instructions (op, d, a, b, x),
the layout of `idc/tools/idrun`. Every value is a float in a slot of the value
stack (an int is a whole float, a string an index into the string pool, a list
an index into the list pool); the compiler knows which, the machine does not.
Every script is a thread with a stack of its own. A frame gives each thread one
turn, in order, and a thread's turn ends where it **yields**: at the end of each
iteration of a `while`, and at a `wait`. A `broadcast` starts the scripts that
run on that message; they get their first turn in the same frame. The clock
runs 33 ms per frame, so output is the same on every run. `blocks run` stops
when no thread is left or after `--frames N` frames (600 by default).

`blocks run` shows the lines said, in order, then the state of every sprite and
variable after the last frame.

## The editor

`blocks edit FILE.blk` opens a window of 960 by 600. The document the editor
holds is the **lines of the file** and nothing else: every edit is an edit of those
lines, so saving writes back the file it read byte for byte until a block is
changed (the examples round-trip, `golden/roundtrip.txt`), a comment or a
test case is shown and kept as it is, and what the checker refuses the editor
can show but not hide.

```
 bar:      [flag] [stop] [Save]   FILE.blk *   N rule violation(s)
 palette   Motion Looks / Control Operators / Variables My Blocks     script area            stage
           the blocks of the category, scrolled by the wheel          (camera: wheel zooms,  sprites, bubbles,
                                                                       a drag on the          a list of them
                                                                       background pans)
```

* **Rendering.** A function is a hat ("when green flag clicked" for `main`,
  "define NAME(...)" for the others) with its statements stacked under it; an
  `if`, `else` or `while` is a C-shaped block with an arm along its body and a
  cap under it; the arguments of a block are slots (pills): white for a plain
  literal or name, coloured for an expression. Colours are the categories'.
  Sprite pages show as banners, `var` lines and test cases as pale strips,
  comments as text. The layout is a pure function of the lines
  (`edit/lay/`, `bke_layout`; `--boxes` prints it).
* **Editing.** Drag a block from the palette into a stack (the bar shows where it
  lands: before or after the row under the pointer, inside the body of a C-shaped
  block, after a whole block when the pointer is on its cap); drag a reporter
  from the palette onto a slot to replace it; drag a block of a stack (an `if`
  takes its `else` with it) to move it, or onto the palette to delete it; click a
  slot to type into it (text, Backspace, Enter to put it in the line, Esc to drop it;
  a click elsewhere puts it in too). Nothing is restructured silently: a block
  lands where it was dropped, with the indent of its place.
* **Rules, live.** After every edit the whole document goes through the checker
  of `blocks check`. A block whose line breaks a rule gets a red outline and,
  while the pointer is on it, a tooltip with what `check` prints for it (message and
  code). A fourth action dropped into a body is accepted and flagged (E0201),
  and the green flag does not run a document that breaks a rule. Editing stops a
  program that is running.
* **Running.** The flag checks, starts `main` afresh and gives the machine one frame
  for each frame of the window; the stage shows each sprite where the machine
  has it (`bkv_sx`), a line out of it in its direction, the bubble of what it said.
* **Files.** The save button writes the file the editor was opened on.

### Headless replay

`blocks edit FILE.blk --script S.txt` plays the script on the same session, without a window, then
prints what `--dump` and `--boxes` ask for and writes `--render-after OUT.ppm`.
A script is one word to a line (blank lines and `#` lines are notes):

```
wheel X Y DY   down X Y [BUTTON [CLICKS]]   up X Y   move X Y   key NAME   text STR   size W H
drag X1 Y1 X2 Y2     press, move through the middle, release (what a hand does)
flag   stop          click the green flag / the stop button
frames N             give the program N frames, as N frames of the window would
save PATH            the document is written to PATH, which is then the editor's file
```

`--dump` prints the camera, the palette's category, the text being typed, the
violations as `check` prints them, whether the program runs and how many frames
it has had, one line for each sprite and the document, each line after `| `.
Pointer positions are the window's (the first script area pixel is at 188, 36).
`golden/*.txt` are scripts over `examples/hello.blk` and `golden/*.out` what they
must print; run them from this directory:

```
blocks.bin edit examples/hello.blk --script golden/drag_run.txt --dump | diff - golden/drag_run.out
blocks.bin edit examples/hello.blk --script golden/e0201.txt    --dump | diff - golden/e0201.out
blocks.bin edit examples/hello.blk --script golden/literal.txt  --dump | diff - golden/literal.out
diff examples/hello.blk golden/literal.saved.blk | diff - golden/literal.diff
```

Headless window: `GFX_MAX_FRAMES=60 idc/tools/headless.sh ./blocks.bin edit examples/tour.blk` (needs Xvfb).

### How it is built

`edit/doc` (the lines of the document: tokens and the spans of a block's slots, kinds,
block edits), `edit/lay` (layout), `edit/pal` (the palette), `edit/ses` (the
session and the reducer `bke_event`, the state, drops, the rule check, the
program's side), `edit/paint`, `edit/win` (the frame loop), `edit/script` (replay
and the state as text). The camera is the graph kit's: the first fifteen cells of
the state are `graph_view_state_` cells and `graph_view_event` is given the wheel and the press
and drag of a pan with an empty view. `bke_event` is pure (lists in, bits out); `bke_step` does what
the bits ask (check, run, save).

## Export to id

`blocks export FILE.blk OUTDIR` applies the rules (it writes nothing and answers
1 when `check` would report something), then writes the program as an id
project and prints each path it wrote, relative to OUTDIR. OUTDIR should be a
new directory: files from an earlier export that this one does not write stay
where they are and make the project fail to build.

```
conf.id                  constants of the runtime (the motion constants, when a sprite moves)
main.id                  main, whichever sprite's page it was on
variables.id             variables_start: every variable set to its declared initial value
SPRITE/NAME.id           a sprite's page (lower case); its functions, named for the first
SPRITE/VARIABLE.id       a variable's setter and getter (VARIABLE_set, VARIABLE_get)
SPRITE/VARIABLE_at.id    VARIABLE_at, when a script assigns an element of the list
runtime/*.id             say and wait, the conversions, the motion blocks and sprite_states;
                         only the parts the program calls
```

A file whose name would be its directory's gets a `_variable` or `_function`
suffix (E0703). Each function is exported with its body and every test case it
carries; `blocks export` is checked by building the result:

```
blocks.bin export examples/tour.blk OUT | diff - golden/export_tour.tree
idc/bin/idc --check OUT
idc/bin/idc OUT -o tour.bin                    # builds, and runs every case in id
./tour.bin | diff - golden/export_tour.out
blocks.bin run examples/tour.blk | sed '/^-- state/,$d' | diff - golden/export_tour.out
```

(`hello`, `counter`, `broadcast` and `tour` each have a `.tree` and `.out`
golden.) What the program said is compared, not the final state `run` prints
after it: the exported program does not print its sprites.

How the blocks map: `main` is `main` and starts with `variables_start()`; a
variable is an export (`(import NAME)` reads it, `NAME_set(v)` writes it,
`NAME_at(i, v)` writes an element), because id lets only the declaring
function assign one; `given NAME = V` is `given NAME_set(V)` and `then NAME:(V)`
is `then NAME_get:(V)`; every case of a function but `main` first runs
`given variables_start`; `say(s)` is `say("SPRITE", s)`, the motion blocks and
`xpos`, `ypos`, `direction` take `(import sprite_states), BASE` first (six cells a
sprite); `int_to_str` and the other conversions are functions of `runtime/`;
`str_to_int` is `to_int`; `insert` and `delete` are `lst_insert`/`lst_delete`
(int lists) or `lst_str_insert`/`lst_str_delete` (string lists); a `return` of
anything but a name or a literal becomes a local of the type
(`result_integer`, ...) and a return of it; a body longer than three actions
once `variables_start()` or such a local is added is split into `chain`
segments of exactly three.

**What the export cannot say yet** (each is refused by `idc --check` when it
happens, never silently different, except where it says "differs"):

* `broadcast` of anything but a string literal: it is written
  `broadcast(EXPR);`, which id has no function for. A literal message is the
  calls of the scripts that run on it, one after another, at the statement, so
  the output **differs** when a script waits and another could have run meanwhile,
  or when the broadcaster says something after the broadcast: the machine
  interleaves the threads by frame, the exported program runs each to its end.
* `wait(s)` is a real `sleep_ms`; the machine's 33 ms frame clock is not modelled.
* `insert` and `delete` on a `float[]`: idstd has the helpers for int and string
  lists only.
* `NAME = []` and `f([])` for a list: id wants a typed context for an empty list
  literal (a declaration), so the setter call is refused.
* a block that holds three actions in `if`/`else` position where the added line
  would cut between an `if` and its `else`, or a nested block that is full and
  gains a line (a return of an expression inside an `if`): chain segments only
  exist at the top of a function.
* three levels of call in one argument (`say(f(g(x)))`) and a parameter or local
  named like a variable: `blocks check` accepts both, id rejects both, so the
  export fails to build. `check` should refuse them (its own rules, stage 2).
* integers: the machine keeps an int in a float (exact to 2^53), the exported
  program in a 64-bit word; they differ only past that.
* `main`'s `argc` and `argv` are the program's own when it runs; the cases pass the
  machine's (`1`, `["blocks"]`).

## What a later milestone needs

* **Editor:** a slot holding an expression is one pill (the expression is not cut
  into nested pills); a function cannot be moved or added from the window, only
  its body; sprite and variable lines are shown, not edited; sprites do not
  have costumes.
