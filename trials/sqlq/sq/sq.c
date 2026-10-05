/* sq.c -- SQLite over small-integer handles. See sq.h. */
#include "sq.h"

#include <sqlite3.h>
#include <stdio.h>
#include <string.h>

#define SQ_DBS 16
#define SQ_STS 256

static sqlite3* sq_db[SQ_DBS];
static unsigned sq_db_gen[SQ_DBS];
static sqlite3_stmt* sq_st[SQ_STS];
static unsigned sq_st_gen[SQ_STS];
static char sq_open_err[256];

/* A handle is (kind << 24) | (generation << 8) | slot. The kind says which
 * table the handle is for, so a connection handed to a statement call is
 * refused instead of being taken for whatever statement holds that slot; the
 * generation is 16 bits, so a stale handle is refused until its slot has been
 * reused 65536 times. Never 0 and never negative. */
#define SQ_KDB 1
#define SQ_KST 2

static int sq_make(unsigned* gen, int s, int kind) {
    return (int)(((unsigned)kind << 24) | ((gen[s] & 0xffff) << 8) | (unsigned)s);
}

/* The slot a handle of this kind names in a table of n entries, or -1 when the
 * handle is of another kind, the wrong generation for its slot, or names none. */
static int sq_slot(const unsigned* gen, int n, int h, int kind) {
    int s = h & 255;
    if (h <= 0 || s >= n || ((unsigned)h >> 24) != (unsigned)kind) return -1;
    return (((unsigned)h >> 8) & 0xffff) == (gen[s] & 0xffff) ? s : -1;
}

static sqlite3* sq_get_db(int h) {
    int s = sq_slot(sq_db_gen, SQ_DBS, h, SQ_KDB);
    return s < 0 ? NULL : sq_db[s];
}

static sqlite3_stmt* sq_get_st(int h) {
    int s = sq_slot(sq_st_gen, SQ_STS, h, SQ_KST);
    return s < 0 ? NULL : sq_st[s];
}

/* A free slot of the connection table, or of the statement table, or -1 when
 * all are in use. A slot is in use while its pointer is set. */
static int sq_free_db(void) {
    for (int i = 0; i < SQ_DBS; i++) if (!sq_db[i]) return i;
    return -1;
}

static int sq_free_st(void) {
    for (int i = 0; i < SQ_STS; i++) if (!sq_st[i]) return i;
    return -1;
}

/* Open the database at path (":memory:" for a private one in memory). The
 * answer is a handle, or -1 with the reason kept for sq_errmsg(-1). */
int id_sq_open(const char* path) {
    int s = sq_free_db();
    sqlite3* d = NULL;
    if (s < 0) { strcpy(sq_open_err, "too many open databases"); return -1; }
    if (sqlite3_open(path, &d) != SQLITE_OK) {
        snprintf(sq_open_err, sizeof sq_open_err, "%s", d ? sqlite3_errmsg(d) : "out of memory");
        sqlite3_close(d);
        return -1;
    }
    sq_db[s] = d;
    sq_db_gen[s] += 1;
    return sq_make(sq_db_gen, s, SQ_KDB);
}

/* Close a connection, and with it any statement still prepared on it (the
 * handles of those become stale). 0, or -1 for a stale handle. */
int id_sq_close(int db) {
    int s = sq_slot(sq_db_gen, SQ_DBS, db, SQ_KDB);
    if (s < 0) return -1;
    for (int i = 0; i < SQ_STS; i++) {
        if (sq_st[i] && sqlite3_db_handle(sq_st[i]) == sq_db[s]) {
            sqlite3_finalize(sq_st[i]);
            sq_st[i] = NULL;
            sq_st_gen[i] += 1;
        }
    }
    sqlite3_close(sq_db[s]);
    sq_db[s] = NULL;
    sq_db_gen[s] += 1;
    return 0;
}

/* Why the last call on db failed. db of -1 asks about the last failed open. */
char* id_sq_errmsg(int db) {
    sqlite3* d = sq_get_db(db);
    if (db == -1) return id_str_of_cstr(sq_open_err);
    return id_str_of_cstr(d ? sqlite3_errmsg(d) : "not an open database handle");
}

/* Rows the last insert, update or delete on db changed, or -1. */
int id_sq_changes(int db) {
    sqlite3* d = sq_get_db(db);
    return d ? sqlite3_changes(d) : -1;
}

/* The rowid the last insert on db made, 0 for none or a stale handle. */
long long id_sq_rowid(int db) {
    sqlite3* d = sq_get_db(db);
    return d ? (long long)sqlite3_last_insert_rowid(d) : 0;
}

char* id_sq_version(void) {
    return id_str_of_cstr(sqlite3_libversion());
}

/* Prepare the first statement of sql on db. A handle, or -1: ask sq_errmsg(db). */
int id_sq_prepare(int db, const char* sql) {
    sqlite3* d = sq_get_db(db);
    int s = sq_free_st();
    sqlite3_stmt* t = NULL;
    if (!d || s < 0) return -1;
    if (sqlite3_prepare_v2(d, sql, -1, &t, NULL) != SQLITE_OK || !t) return -1;
    sq_st[s] = t;
    sq_st_gen[s] += 1;
    return sq_make(sq_st_gen, s, SQ_KST);
}

int id_sq_step(int st) {
    sqlite3_stmt* t = sq_get_st(st);
    return t ? sqlite3_step(t) : -1;
}

int id_sq_finalize(int st) {
    int s = sq_slot(sq_st_gen, SQ_STS, st, SQ_KST);
    if (s < 0) return -1;
    sqlite3_finalize(sq_st[s]);
    sq_st[s] = NULL;
    sq_st_gen[s] += 1;
    return 0;
}

/* Run the statement again from its start, with its bindings kept. */
int id_sq_reset(int st) {
    sqlite3_stmt* t = sq_get_st(st);
    return t ? sqlite3_reset(t) : -1;
}

/* The binds answer SQLite's code (0 is ok) or -1 for a stale handle. Parameters
 * count from 1, as in SQLite. */
int id_sq_bind_int(int st, int idx, long long v) {
    sqlite3_stmt* t = sq_get_st(st);
    return t ? sqlite3_bind_int64(t, idx, (sqlite3_int64)v) : -1;
}

int id_sq_bind_text(int st, int idx, const char* s) {
    sqlite3_stmt* t = sq_get_st(st);
    return t ? sqlite3_bind_text(t, idx, s, -1, SQLITE_TRANSIENT) : -1;
}

/* Bind n bytes at addr in the store as a blob. SQLite copies them
 * (SQLITE_TRANSIENT) because the store moves when anything allocates. */
int id_sq_bind_blob(int st, int idx, long long addr, int n) {
    sqlite3_stmt* t = sq_get_st(st);
    if (!t) return -1;
    if (n <= 0) return sqlite3_bind_zeroblob(t, idx, 0);
    return sqlite3_bind_blob(t, idx, id_store_span(addr, n), n, SQLITE_TRANSIENT);
}

/* Columns of the result, or -1. Columns count from 0. */
int id_sq_cols(int st) {
    sqlite3_stmt* t = sq_get_st(st);
    return t ? sqlite3_column_count(t) : -1;
}

/* 1 integer, 2 float, 3 text, 4 blob, 5 null: SQLite's own codes. */
int id_sq_ctype(int st, int col) {
    sqlite3_stmt* t = sq_get_st(st);
    return t ? sqlite3_column_type(t, col) : -1;
}

int id_sq_cbytes(int st, int col) {
    sqlite3_stmt* t = sq_get_st(st);
    return t ? sqlite3_column_bytes(t, col) : -1;
}

long long id_sq_cint(int st, int col) {
    sqlite3_stmt* t = sq_get_st(st);
    return t ? (long long)sqlite3_column_int64(t, col) : 0;
}

/* The column as text, as an id string: a NUL inside it ends the string. */
char* id_sq_ctext(int st, int col) {
    sqlite3_stmt* t = sq_get_st(st);
    const unsigned char* p = t ? sqlite3_column_text(t, col) : NULL;
    return id_str_of_cstr(p ? (const char*)p : "");
}

/* Copy up to cap bytes of the column's blob to dst in the store. Answers the
 * blob's whole length, so a caller that sized dst from sq_cbytes sees every byte
 * arrive, and one that did not can tell it was cut short. */
int id_sq_cblob(int st, int col, long long dst, int cap) {
    sqlite3_stmt* t = sq_get_st(st);
    if (!t) return -1;
    const void* p = sqlite3_column_blob(t, col);
    int n = sqlite3_column_bytes(t, col);
    int k = n < cap ? n : cap;
    if (p && k > 0) memcpy(id_store_span(dst, k), p, (size_t)k);
    return n;
}
