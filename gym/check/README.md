# gym/check: deciding whether an answer is right

`check_answer(kind, reference, tolerance, attempt)` answers `correct`,
`incorrect` or `unparseable`; `check_normal(kind, attempt)` answers the normalised
form (the text the log stores). Neither can trap on any text a learner can type.

| kind | learner input accepted | compared |
| --- | --- | --- |
| `integer` | optional sign and digits only (`42`, `-3`, `+7`, `- 3`); `3.0` and `7/2` are unparseable | exactly |
| `fraction` | any number: `3/8`, `6/16`, `-3/8`, `3/-8`, `0.375`, `.375`, `+.5`, `37.5%`, `3 / 8` | exactly, as lowest-terms fractions |
| `percent` | the same numbers; `37.5%` is 3/8, `37.5` alone is 75/2 | exactly |
| `decimal` | the same numbers | within the item's absolute `tolerance`, inclusive, at a billionth of a unit |
| `choice` | one letter, any case, with brackets or a full stop (`(b)`, `B.`); letters mixed with digits or other letters are unparseable | the letter |
| `text` | any non-blank text | lower-cased, white space collapsed |

- Numbers are exact fractions of two `word`s, never floats. At most 18 digits per
  number and never an overflow: a product that would pass 2^63 makes the answer
  unparseable instead of wrong.
- Spaces are allowed only next to a sign, a slash or a percent sign. `1 1/2` and
  `3 8` are unparseable, not 11/2 or 38.
- Normalised numbers are lowest terms with no plus sign: `3/8`, `-3/8`, `7`.
- An item whose own reference answer cannot be read also answers `unparseable`;
  `check_problem(kind, reference, tolerance)` says why in words, and `pack check`
  uses it to refuse such items.
- Decimal tolerance: both values are cut towards zero to a billionth and compared
  as whole numbers, so `0.51` against `0.5` with tolerance `0.01` is correct
  (binary floats get this wrong). Values above 9e9 are compared exactly.

## `set`, `truth` and `free`

| kind | learner input accepted | compared |
| --- | --- | --- |
| `set` | a finite set such as `{1, 2, {3}}`; members are integers (`007` is `7`), short words (letters, digits, `-`, `_`, `.`, at most 24 bytes, any case) and ordered pairs or tuples `(a, b)`, nested to any depth; white space is free | by canonical text: members sorted and repeats dropped, so `{2, 1, 1}` equals `{1, 2}`; tuples keep their order, so `(1, 2)` differs from `(2, 1)` |
| `truth` | a column of `T` and `F`, any case, spaces and line breaks ignored (`t f f t`), at most 64 letters | the letters |
| `free` | any non-blank text | never decided by the checker: `check_answer` answers `pending`, and the session sends it to the grader or to the learner |

- A set that is not well formed (an unclosed bracket, an empty member such as `{1,,2}` or `{1,}`, a stray
  character, `()`) is `unparseable`, never wrong; so is a blank free answer. `check_normal` gives the canonical
  text the log stores (`{1,2}`, `TFFT`, a collapsed free answer).
- `{}` is the empty set; `{{}}` is a set holding it; `{1, {1}}` has two members.
