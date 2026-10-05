/* zl.h -- the C target's realisation of the `zl` backend ABI: zlib's gzip
 * format over the flat store. The contract is the `native` declarations beside
 * this file; this header is the C prototypes of one target's answer to them.
 *
 * Buffers are addresses in the flat store (id `word`). A native turns an
 * address and a length into a pointer with id_store_span, which the generated
 * program exports and which traps on a range outside the store, so a wrong
 * length is a clean abort and never a wild write. Take every span you need
 * BEFORE calling into zlib and do not call anything that allocates in the
 * store in between: an alloc may move the store and every span with it.
 *
 * Results: a count of bytes (>= 0), or one of the negatives below. The zlib
 * codes are passed through unchanged (-2 stream error, -3 data error, -4 out
 * of memory); two are added because zlib's -5 cannot say which side ran out.
 */
#ifndef ID_ZL_H
#define ID_ZL_H

#define ZL_OUT_FULL (-100)
#define ZL_IN_SHORT (-101)

extern unsigned char* id_store_span(long long addr, long long n);
extern char* id_str_of_cstr(const char* p);

extern int id_zl_bound(int n, int level);
extern int id_zl_gzip(long long src, int n, long long dst, int cap, int level);
extern int id_zl_gunzip(long long src, int n, long long dst, int cap);
extern long long id_zl_crc32(long long src, int n, long long seed);
extern char* id_zl_version(void);

#endif
