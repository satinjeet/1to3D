#!/usr/bin/env python3
"""Serve a design's browser/ folder over http and open it, or take headless screenshots of it.

    serve_viewer.py designs/<slug>/browser              # serve until killed, open the default browser
    serve_viewer.py designs/<slug>/browser --no-open    # serve only
    serve_viewer.py designs/<slug>/browser --shots      # headless chromium shots into browser/shots/, then exit
    serve_viewer.py designs/<slug>/browser --stop       # stop a server started for this folder

The viewer fetches manifest.json and STL files, so file:// does not work; it needs http.
"""
import argparse
import functools
import http.server
import os
import shutil
import signal
import subprocess
import sys
import threading
import webbrowser


PIDFILE = ".server.pid"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def translate_path(self, path):
        # Refuse anything (symlinks included) that resolves outside the served folder.
        p = os.path.realpath(super().translate_path(path))
        root = os.path.realpath(self.directory)
        return p if p == root or p.startswith(root + os.sep) else os.path.join(root, ".outside-root")  # does not exist, so 404


def start(root, preferred):
    """Bind the preferred port, or any free one; binding here avoids a check-then-bind race."""
    handler = functools.partial(QuietHandler, directory=root)
    try:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", preferred), handler)
    except OSError:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def stop(root):
    path = os.path.join(root, PIDFILE)
    try:
        with open(path) as f:
            pid = int(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        sys.exit("no running viewer recorded in %s" % root)
    # The pid file sits in the project, so check the pid is really this script before signalling it.
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            if b"serve_viewer.py" not in f.read():
                sys.exit("pid %d in %s is not a viewer; not stopping it" % (pid, path))
    except FileNotFoundError:
        pass  # no /proc entry: the process is gone, or not Linux; os.kill below sorts it out
    try:
        os.kill(pid, signal.SIGTERM)
        print("stopped viewer", pid)
    except ProcessLookupError:
        print("viewer %d was not running" % pid)
    os.remove(path)


def find_chromium():
    for name in ("chromium", "chromium-browser", "google-chrome-stable", "google-chrome"):
        p = shutil.which(name)
        if p:
            return p
    return None


def shots(url, out_dir, views, size):
    exe = find_chromium()
    if not exe:
        sys.exit("no chromium/chrome found for headless shots")
    os.makedirs(out_dir, exist_ok=True)
    for v in views:
        out = os.path.join(out_dir, "%s.png" % v)
        subprocess.run([
            exe, "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
            "--hide-scrollbars", "--window-size=%d,%d" % size, "--virtual-time-budget=15000",
            "--screenshot=%s" % out, "%s?view=%s" % (url, v),
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        print(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("browser_dir")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--shots", action="store_true", help="headless screenshots, then exit")
    ap.add_argument("--stop", action="store_true", help="stop a server started for this folder")
    ap.add_argument("--views", default="iso,front,top,right")
    ap.add_argument("--size", default="1400x1000")
    a = ap.parse_args()

    root = os.path.abspath(a.browser_dir)
    if a.stop:
        stop(root)
        return
    if not os.path.isfile(os.path.join(root, "manifest.json")):
        sys.exit("no manifest.json in %s; run Design.export_browser() first" % root)
    srv = start(root, a.port)
    url = "http://127.0.0.1:%d/index.html" % srv.server_address[1]

    if a.shots:
        w, h = (int(x) for x in a.size.split("x"))
        shots(url, os.path.join(root, "shots"), a.views.split(","), (w, h))
        srv.shutdown()
        return
    pidfile = os.path.join(root, PIDFILE)
    with open(pidfile, "w") as f:
        f.write("%d %s\n" % (os.getpid(), url))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    print("viewer at", url, flush=True)
    if not a.no_open:
        webbrowser.open(url)
    try:
        threading.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        srv.shutdown()
        try:
            os.remove(pidfile)
        except OSError:
            pass


if __name__ == "__main__":
    main()
