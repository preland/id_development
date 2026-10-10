# The subject pack format

A pack is a directory of plain `.txt` files that a person can write by hand in
any editor. It holds the **concepts** of one subject and the **items** (practice
questions) that test them. No JSON, no tools: one line, one fact.

`gym/packs/probability/` is a complete example; `pack check` (below) validates
any pack. Other files in the directory (`notes.md`, images) are ignored, and
files may sit in subdirectories: all `.txt` files below the pack directory are
read, in path order.

## Lines

Every line is one of:

```
# a comment: ignored (but still counted in line numbers)
<blank>: ignored
key: value
```

- The **key** is the text before the first colon: lower case letters, digits and
  underscores, no spaces. Keys are not case sensitive.
- The **value** is everything after the first colon, trimmed. It may contain more
  colons. A value is one line; there are no continuation lines. Write a multiple
  choice item's options inline: `A) 1/3 B) 1/2 C) 2/3`.
- A `concept:` or `item:` line **starts a block**; the lines after it, up to the
  next `concept:` or `item:` line, belong to it. A field before the first block
  is an error.
- A key a block must have is "missing" when it is absent or its value is blank.
- A key may be written once, except `misconception` and `rubric`, which repeat.

## A concept

```
concept: bayes_rule
name: Bayes' rule
summary: One line saying what the idea is.
requires: conditional, complement
source: The passage this concept is grounded in.
misconception: A known wrong belief about it.
misconception: Another one.
```

| key | needed | meaning |
| --- | --- | --- |
| `concept` | yes | the id: letters, digits, underscores; unique among concepts |
| `name` | yes | the title shown to the learner |
| `summary` | yes | one line |
| `source` | yes | the source passage the concept comes from (P12: nothing unsourced) |
| `requires` | no | comma-separated ids of concepts that must come first |
| `misconception` | no, repeats | a wrong belief learners commonly hold |

## An item

```
item: bayes_1
concepts: bayes_rule
kind: solve
answer_kind: fraction
difficulty: 1100
transfer: no
verified: tool
prompt: The question, on one line.
answer: 1/12
rubric: What a good solution shows.
hint_nudge: Rung 1.
hint_question: Rung 2.
hint_step: Rung 3.
hint_example: Rung 4.
```

| key | needed | meaning |
| --- | --- | --- |
| `item` | yes | the id: unique among items |
| `concepts` | yes | comma-separated concept ids the item tests (at least one) |
| `kind` | yes | `recall`, `solve`, `estimate`, `choice` or `error_hunt` |
| `answer_kind` | yes | how the checker reads the answer (below) |
| `tolerance` | decimal items | the largest allowed distance from `answer`, a number such as `0.01` |
| `difficulty` | yes | a rating from 100 to 3000 (an Elo-style number; 1000 is average) |
| `transfer` | no | `yes` marks a held-out item that is never used in practice; `no` (the default) otherwise |
| `verified` | yes | `tool` (checked by computing it), `source` (taken from a cited source) or `unverified` |
| `prompt` | yes | the question |
| `answer` | yes | the reference answer, written so the checker can read it |
| `rubric` | yes, repeats | what a good solution shows; one line per point |
| `hint_nudge`, `hint_question`, `hint_step`, `hint_example` | yes, all four | the **hint ladder**, exactly four rungs |

An item of `kind: choice` must have `answer_kind: choice`.

### The hint ladder

Four rungs, least help first (design principle P4):

1. `hint_nudge`: a nudge in the right direction.
2. `hint_question`: a guiding question.
3. `hint_step`: a partial step.
4. `hint_example`: a fully worked example, which does contain the answer.

Rungs 1 to 3 must **not** contain the answer. `pack check` cannot decide that for
free text, so it is a rule for the author and the reviewer; the probability pack
was read for it by hand.

### Answer kinds

| `answer_kind` | the learner may write | `answer` is written as |
| --- | --- | --- |
| `integer` | `42`, `-3`, `+7`, `42` with spaces around it | an integer |
| `fraction` | `3/8`, `6/16`, `-3/8`, `0.375`, `.375`, `37.5%`: any number, compared exactly | `3/8` |
| `decimal` | any number, accepted when within `tolerance` of the answer | `0.4167` |
| `percent` | `37.5%`, `0.375`, `3/8`: any number, compared exactly | `37.5%` |
| `choice` | one letter, in any case, with or without brackets or a full stop | `B` |
| `text` | any text, compared after lower-casing and collapsing white space | `yes` |

Numbers have at most 18 digits (more is read as unparseable, never as a wrong
number). See `gym/check/` for the exact rules.

## Transfer items

`transfer: yes` items are the held-out probes that measure whether an idea
carries to a new setting. They are never practised, so every concept an item
lists in `concepts` also needs at least one ordinary item (without `transfer:
yes`) for the learner to practise on.

## `pack check DIR`

`pack_check(DIR)` loads the pack and answers a list of problems, each as
`file:line: message`, in the order the rules ran. An empty list means the pack is
good. It reports:

- a directory that is not one, no `.txt` files, or no concepts or items;
- a line that is not `key: value`, or a field before any block;
- an unknown key, or a key written twice that the format reads once;
- a missing or blank required key;
- a **missing hint rung**, naming the rung that is absent;
- a concept id in `requires` or `concepts` that is not defined, or a concept
  requiring itself;
- a **duplicate id** among concepts or among items (at the later one, with the
  line of the first);
- a `kind`, `verified`, `transfer` or `difficulty` that is not one of the allowed
  values;
- a **reference answer the checker cannot read** for its `answer_kind`, an unknown
  `answer_kind`, or a decimal item with no (or a bad) `tolerance`;
- a **transfer item with no practice sibling** for one of its concepts.

Not checked: cycles in `requires`, whether a hint rung leaks the answer, whether
the answer is actually right (`verified` says how it was established).
