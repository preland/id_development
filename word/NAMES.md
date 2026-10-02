# word/ vocabulary

`word/` is one compilation unit, so a variable or parameter name has one type across the whole tree (docs/PROJECT.md section 5, pitfall 6) and function names are program-wide. Struct field names are scoped to their struct and do not count.

This file records what `word/core/doc` (B1) already uses. Reuse the same name for the same type, and pick another name where your type needs one that is taken.

## Names taken, by type

| type | names |
| --- | --- |
| `Doc` | `d` |
| `Body` | `b` |
| `Fmt` | `f` |
| `Para` | `p`, `np` |
| `Para[]` | `pl` |
| `Text` | `t`, `u`, `nt` |
| `Tab` | `tb`, `chars`, `tc`, `tp` |
| `Pos` | `pa`, `pb` (not `p`: that is a `Para`) |
| `Run` | `ru`, `rv`, `nr`, `cur`, `head` |
| `Run[]` | `rs`, `tr`, `src`, `dst` |
| `Style`, `Sty`, `ListDef`, `Page`, `Ext`, `Lay`, `Model` | `st`, `sy`, `ld`, `pg`, `x`, `ly`, `mo` |
| `int[]` | `cps`, `runs`, `row`, `rows`, `rg`, `sx`, `sp`, `wr`, `acc`, `ins`, `fm`, `vs`, `ws`, `none`, `sls`, `fc`, `fp`, `fl`, `lines`, `pen`, `rel`, `size`, `margin`, `hf`, `levels` |
| `string` | `name`, `text`, `font` |
| `int` | every other short name used as a loop counter, offset or result: `i j k n m w h id at off lo hi cp cprop pprop field value key val bits on mode kind which code lk res got sn ia iz begin same` |

## Where the seams of docs/WORD.md collide with that

* 4.2 `Fmt f` and 4.4 `face_for(Face f, Fmt fmt, ...)`: `f` is a `Fmt` here, so a `Face` needs another name.
* 4.2 `Tab t` is `tb` here, because `t` is a `Text`.
* 4.3 and 4.4 `Pos p` collides with `Para p`: use `ps` or another name for a `Pos`.
* 4.4 `View v`, 4.8 `Ribbon r`, `App a`, 4.3 `Sel s`, and `Pos from`, `Pos hit`, `Pos out`: B1 has none of `v r a s from hit out` as a variable name.

## Prefixes

`doc_ para_ pos_ tab_ fmt_ style_ text_ body_ page_ ext_ paras_ run_ rs_ runs_ cps_ tab_ flag_` belong to the model; `op_ rng_ rand_ flat_ model_ script_ dump_` belong to its checks and the seeded script.

## Ribbon (B7a, `ui/ribbon/model`)

Its constants in conf.id sit between the `B7a begin/end` markers. Its tab ids are `rib_tab_file rib_tab_home rib_tab_insert rib_tab_layout rib_tab_view rib_tab_qat`, not `tab_*`, because `tab_` is the model's function prefix (`tab_home` is a function there).

Where the ribbon needed a name the model already holds for another type it took an `r` prefixed one:

| name | type | instead of |
| --- | --- | --- |
| `rrow` | `int` (a row of the `rb_*` tables) | `row`, an `int[]` in the model |
| `rhead` | `string` (a tooltip head) | `head`, a `Run` |
| `rpa`, `rpb` | `int[]` (id lists) | `pa`, `pb`, a `Pos` |
| `rp` | `int` (a rect offset) | `p`, a `Para` |
| `rst` | `int[]` (a group step) | `st`, a `Style` |
| `rcur` | `int[]` (a cursor per row) | `cur`, a `Run` |
| `rx` | `int` | `x`, an `Ext` |
