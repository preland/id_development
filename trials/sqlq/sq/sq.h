/* sq.h -- the C target's realisation of the `sq` backend ABI: SQLite's
 * connection and prepared-statement API as small integers.
 *
 * The contract is the `native` declarations below this directory; this header
 * is one target's answer to them. Every native takes and returns `int` or
 * `word`, a string, or an address in the flat store.
 *
 * Handles. An id value cannot hold a C pointer, so a connection or a statement
 * is an index into a table kept here, and what id sees is that index. The index
 * carries a kind and a generation: a handle is (kind << 24) | (generation << 8)
 * | slot. A slot's generation advances each time it is released, so a handle
 * that outlived its statement is refused with -1 and never reaches the
 * statement that now holds the slot, and the kind (1 connection, 2 statement)
 * makes a connection handed to a statement call refused the same way. 16
 * connections and 256 statements may be open at once.
 *
 * Results. A handle >= 1, or -1 for a full table, a refused call or a stale
 * handle (a connection's reason is sq_errmsg). A step answers SQLite's own
 * code: 100 a row is ready, 101 done, anything else an error (-1 for a stale
 * handle). Bytes cross as store addresses, as in zl.h: take the span after the
 * last call that can allocate, and expect the store to move on the next one.
 */
#ifndef ID_SQ_H
#define ID_SQ_H

extern unsigned char* id_store_span(long long addr, long long n);
extern char* id_str_of_cstr(const char* p);

extern int id_sq_open(const char* path);
extern int id_sq_close(int db);
extern char* id_sq_errmsg(int db);
extern int id_sq_changes(int db);
extern long long id_sq_rowid(int db);
extern char* id_sq_version(void);

extern int id_sq_prepare(int db, const char* sql);
extern int id_sq_step(int st);
extern int id_sq_finalize(int st);
extern int id_sq_reset(int st);
extern int id_sq_bind_int(int st, int idx, long long v);
extern int id_sq_bind_text(int st, int idx, const char* s);
extern int id_sq_bind_blob(int st, int idx, long long addr, int n);

extern int id_sq_cols(int st);
extern int id_sq_ctype(int st, int col);
extern int id_sq_cbytes(int st, int col);
extern long long id_sq_cint(int st, int col);
extern char* id_sq_ctext(int st, int col);
extern int id_sq_cblob(int st, int col, long long dst, int cap);

#endif
