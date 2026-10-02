# httpd

Static-file HTTP/1.1 server (GET, HEAD) written in `id`.

    httpd --root DIR [--port N] [--host ADDR]

With `--port N` it listens on `ADDR:N` (default `127.0.0.1`; `--port 0` takes an
ephemeral port and the banner on stderr names it) and serves many clients from
one process: `sock_poll` waits on the listener and every open connection, and
each readable connection is served one request at a time. Without `--port` it
serves one connection on stdin/stdout, inetd style, as before.

    httpget HOST PORT PATH        (../httpget: an id client over real TCP)

## Limits

- Concurrency is one process, one thread, one poll loop. Idle keep-alive
  connections cost nothing, but a connection that has begun a request and then
  stalls holds the loop for up to `hd_net_ms` (2000 ms) per byte read before it
  is answered 400 and dropped. There is no per-connection read state machine.
- At most `hd_max_conns` (32) connections are held; a newer one evicts the oldest.
- `--host` must be a numeric address (`0.0.0.0` to expose it, `::1` for IPv6).
- The access log goes to stderr: `PEER - - [-] "REQUEST LINE" STATUS BODYBYTES`.
  There is still no timestamp in it.
- No `Date` header (no wall clock). Symlinks inside the root are followed.
- Not implemented: Range, ETag/If-None-Match, chunked request bodies (rejected
  with 400), request bodies (skipped up to 1 MiB, larger is 413), pipelining
  beyond read order, TLS.
- Extra status: 301 for a directory requested without trailing slash.
- Per-request allocation (`sock_peer`, strings) is not freed until exit.
