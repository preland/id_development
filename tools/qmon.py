#!/usr/bin/env python3
"""Drive the kernel under QEMU: type at it, photograph it, read what it said.

A graphical kernel cannot be tested by reading stdout, and QEMU's text monitor
over a pipe drops input in a way that depends on timing. QMP is a socket and a
JSON protocol, so a test can wait for the machine to be ready, send keys, ask
for the framebuffer, and know each one happened.

    tools/qmon.py build/kernel.elf --wait 2 --keys "l s enter" --shot out.ppm

Keys are QEMU key names separated by spaces (`a`, `enter`, `spc`, `minus`),
which is what `send-key` takes. Serial output goes to stdout.
"""
import argparse, json, os, socket, subprocess, sys, tempfile, time


class Qmp:
    def __init__(self, path):
        self.s = socket.socket(socket.AF_UNIX)
        for _ in range(200):
            try:
                self.s.connect(path)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                time.sleep(0.05)
        else:
            sys.exit("qmon: QEMU never opened its QMP socket")
        self.f = self.s.makefile("rw")
        self.f.readline()                      # the greeting
        self.cmd("qmp_capabilities")

    def cmd(self, name, **args):
        self.f.write(json.dumps({"execute": name, "arguments": args}) + "\n")
        self.f.flush()
        while True:
            line = self.f.readline()
            if not line:
                sys.exit(f"qmon: QEMU closed the connection during {name}")
            msg = json.loads(line)
            if "event" in msg:
                continue
            if "error" in msg:
                sys.exit(f"qmon: {name}: {msg['error']['desc']}")
            return msg.get("return")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kernel")
    ap.add_argument("--wait", type=float, default=2.0,
                    help="seconds to let the machine boot before typing")
    ap.add_argument("--keys", default="",
                    help="QEMU key names, space separated; '|' pauses briefly")
    ap.add_argument("--settle", type=float, default=1.0,
                    help="seconds to wait after the last key")
    ap.add_argument("--shot", help="write the framebuffer here, as PPM")
    ap.add_argument("--serial", help="write the serial output here")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="qmon.")
    sock = os.path.join(tmp, "qmp")
    serial = args.serial or os.path.join(tmp, "serial")
    qemu = ["qemu-system-x86_64", "-kernel", args.kernel,
            "-display", "none", "-vga", "std", "-no-reboot",
            "-serial", "file:" + serial,
            "-qmp", f"unix:{sock},server,nowait"]
    proc = subprocess.Popen(qemu, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    try:
        q = Qmp(sock)
        time.sleep(args.wait)
        for tok in args.keys.split():
            if tok == "|":
                time.sleep(0.3)
                continue
            q.cmd("send-key", keys=[{"type": "qcode", "data": tok}])
            time.sleep(0.03)
        time.sleep(args.settle)
        if args.shot:
            q.cmd("screendump", filename=os.path.abspath(args.shot))
        q.cmd("quit")
    finally:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    if os.path.exists(serial):
        sys.stdout.write(open(serial, errors="replace").read())


main()
