/* zl.c -- zlib's gzip format over the flat store. See zl.h. */
#include "zl.h"

#include <zlib.h>
#include <string.h>

/* The most bytes gzip output of n input bytes can take at this level,
 * header and trailer included: deflateBound on a gzip-wrapped stream. -1 when
 * the level is not one zlib accepts. */
int id_zl_bound(int n, int level) {
    z_stream z;
    memset(&z, 0, sizeof z);
    if (n < 0 || deflateInit2(&z, level, Z_DEFLATED, 31, 8, Z_DEFAULT_STRATEGY) != Z_OK) return -1;
    uLong b = deflateBound(&z, (uLong)n);
    deflateEnd(&z);
    return b > 2147483647UL ? -1 : (int)b;
}

/* Compress n bytes at src into at most cap bytes at dst, as one gzip member
 * with no name and a zero mtime (what `gzip -n` writes). Answers the bytes
 * written, or a negative zlib code. */
int id_zl_gzip(long long src, int n, long long dst, int cap, int level) {
    z_stream z;
    memset(&z, 0, sizeof z);
    unsigned char* s = id_store_span(src, n);
    unsigned char* d = id_store_span(dst, cap);
    int r = deflateInit2(&z, level, Z_DEFLATED, 31, 8, Z_DEFAULT_STRATEGY);
    if (r != Z_OK) return r;
    z.next_in = s; z.avail_in = (uInt)n;
    z.next_out = d; z.avail_out = (uInt)cap;
    r = deflate(&z, Z_FINISH);
    int out = (int)z.total_out;
    deflateEnd(&z);
    if (r == Z_STREAM_END) return out;
    return r == Z_OK || r == Z_BUF_ERROR ? ZL_OUT_FULL : r;
}

/* Decompress the gzip members at src (n bytes), one after another as gzip
 * does, into at most cap bytes at dst. Answers the bytes written, ZL_OUT_FULL
 * when dst filled before the input ended (try a larger one), ZL_IN_SHORT when
 * the input ended inside a member, or a negative zlib code. */
int id_zl_gunzip(long long src, int n, long long dst, int cap) {
    z_stream z;
    memset(&z, 0, sizeof z);
    unsigned char* s = id_store_span(src, n);
    unsigned char* d = id_store_span(dst, cap);
    int r = inflateInit2(&z, 31);
    if (r != Z_OK) return r;
    z.next_in = s; z.avail_in = (uInt)n;
    z.next_out = d; z.avail_out = (uInt)cap;
    long long done = 0;
    for (;;) {
        r = inflate(&z, Z_NO_FLUSH);
        if (r != Z_STREAM_END || z.avail_in == 0) break;
        done += (long long)z.total_out;
        if (inflateReset(&z) != Z_OK) break;
    }
    int out = (int)(done + (long long)z.total_out);
    int full = z.avail_out == 0;
    inflateEnd(&z);
    if (r == Z_STREAM_END) return out;
    if (r == Z_OK || r == Z_BUF_ERROR) return full ? ZL_OUT_FULL : ZL_IN_SHORT;
    return r;
}

/* zlib's crc32 of n bytes at src, continuing from seed (0 to start). The
 * answer is the 32-bit value, never negative. */
long long id_zl_crc32(long long src, int n, long long seed) {
    unsigned char* s = id_store_span(src, n);
    return (long long)crc32((uLong)seed, s, (uInt)n);
}

/* zlib's version string, as an id string. */
char* id_zl_version(void) {
    return id_str_of_cstr(zlibVersion());
}
