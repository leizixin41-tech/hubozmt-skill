"""极简 Chrome DevTools 协议客户端(只用标准库):启动无界面 Chrome、执行 JS、截图。"""
import base64, json, os, random, socket, struct, subprocess, tempfile, time, urllib.request, shutil

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class WS:
    def __init__(self, url):
        assert url.startswith("ws://")
        hostport, path = url[5:].split("/", 1)
        host, port = hostport.split(":")
        self.s = socket.create_connection((host, int(port)))
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.s.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(4096)
        assert b" 101 " in buf.split(b"\r\n")[0], buf[:200]
        self.rest = buf.split(b"\r\n\r\n", 1)[1]

    def _read(self, n):
        while len(self.rest) < n:
            chunk = self.s.recv(max(65536, n - len(self.rest)))
            if not chunk:
                raise ConnectionError("websocket closed")
            self.rest += chunk
        out, self.rest = self.rest[:n], self.rest[n:]
        return out

    def send(self, text):
        data = text.encode()
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126); hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127); hdr += struct.pack(">Q", n)
        mask = os.urandom(4)
        hdr += mask
        self.s.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)) if n < 4096
                       else bytes(hdr) + _xor(data, mask))

    def recv(self):
        msg = b""
        while True:
            b0, b1 = self._read(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            payload = self._read(n)
            op = b0 & 0x0F
            if op == 9:  # ping
                continue
            msg += payload
            if b0 & 0x80:
                return msg.decode()


def _xor(data, mask):
    import numpy as np
    a = np.frombuffer(data, np.uint8)
    m = np.frombuffer(mask * (len(data) // 4 + 1), np.uint8)[:len(data)]
    return (a ^ m).tobytes()


_NOPROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Browser:
    """一个无界面 Chrome 实例 + 一个页面。"""

    def __init__(self, w, h, proxy=None):
        self.port = random.randint(20000, 40000)
        self.prof = tempfile.mkdtemp(prefix="hzcdp_")
        args = [CHROME, "--headless=new", f"--remote-debugging-port={self.port}", f"--user-data-dir={self.prof}",
                f"--window-size={w},{h}", "--hide-scrollbars", "--force-device-scale-factor=1",
                "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                "--allow-file-access-from-files", "--force-color-profile=srgb", "about:blank"]
        if proxy:
            args.insert(1, f"--proxy-server={proxy}")
        self.p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        page = None
        for _ in range(200):
            try:
                tabs = json.load(_NOPROXY.open(f"http://127.0.0.1:{self.port}/json", timeout=2))
                page = [t for t in tabs if t["type"] == "page"][0]
                break
            except Exception:
                time.sleep(0.1)
        if page is None:
            raise RuntimeError("Chrome 调试端口没起来")
        self.ws = WS(page["webSocketDebuggerUrl"])
        self.i = 0
        self.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)

    def call(self, method, **params):
        self.i += 1
        self.ws.send(json.dumps({"id": self.i, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.i:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})

    def js(self, expr, await_promise=True):
        r = self.call("Runtime.evaluate", expression=expr, awaitPromise=await_promise, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(json.dumps(r["exceptionDetails"])[:800])
        return r.get("result", {}).get("value")

    def goto(self, url, wait_expr="document.readyState==='complete'", timeout=30):
        self.call("Page.enable")
        self.call("Page.navigate", url=url)
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.js(wait_expr, False):
                    return
            except Exception:
                pass
            time.sleep(0.1)
        raise TimeoutError(url)

    def shot(self, fmt="jpeg", quality=94):
        p = dict(format=fmt, captureBeyondViewport=False, optimizeForSpeed=bool(int(os.environ.get("HZ_FAST", "0"))))
        if fmt == "jpeg":
            p["quality"] = quality
        return base64.b64decode(self.call("Page.captureScreenshot", **p)["data"])

    def close(self):
        try:
            self.p.terminate(); self.p.wait(5)
        except Exception:
            self.p.kill()
        shutil.rmtree(self.prof, ignore_errors=True)
