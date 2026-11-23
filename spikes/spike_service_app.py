"""Spike: minimal HTTP service + heartbeat recorder.
Heartbeat lines: wall_clock monotonic pid boot_id. A wall-clock gap much larger than the
interval with the same pid = the Sprite paused and resumed the process; a new pid = restart."""
import http.server, os, threading, time
LOG = os.path.expanduser("~/leakwatch/spikes/heartbeat.log")
BOOT = open("/proc/sys/kernel/random/boot_id").read().strip()
def beat():
    while True:
        with open(LOG, "a") as f:
            f.write(f"{time.time():.0f} {time.monotonic():.0f} {os.getpid()} {BOOT}\n")
        time.sleep(10)
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"spike pid={os.getpid()} boot={BOOT[:8]}\n".encode()
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
threading.Thread(target=beat, daemon=True).start()
http.server.ThreadingHTTPServer(("0.0.0.0", 8080), H).serve_forever()
