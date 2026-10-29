"""截图素材(只截图,不下载视频)。

用法:
  hz capture url   <网址> <输出.png> [--size 1600x1000] [--wait 8] [--full]
                   [--scale 2] [--el <选择器>] [--pad 12] [--box 名字=<选择器> ...]
        --el 只截这个元素(局部图,比如 GitHub 的仓库头、README 某一节);--scale 2 按 2 倍清晰度截(局部图上屏放大也不糊);
        --box 量出某个元素在截图里的位置,写进同名 .json 的 boxes(0–1 的比例 [x,y,宽,高]),合成师用 hz.k.shot(...).box("名字") 直接框选。
        选择器可以是 CSS 选择器,也可以写 @文字(找包含这段文字的最小元素);末尾加 ^ = 取它所在的按钮/链接/列表项整体,^^ 再往外一层(如整个列表)。
        例(GitHub 仓库页):--box star=@Star^ --box fork=@Fork^ --box about=@About
        --theme light|dark 指定网页用浅色/深色主题(默认跟网站);--hide <选择器> 截图前隐藏 Cookie 弹窗、登录条等(可写多个)
  hz capture tweet <推文网址> <输出.png> [--theme dark|light]
        截推特官方渲染的公开推文卡片(含头像、认证、点赞数),不需要登录、不收费;保留作者名和账号。
        遇到删帖/私密/限制嵌入的推文会失败,换一条即可。
  hz capture yt    <YouTube 网址或视频ID> <输出.png> [--t 秒]
        打开视频页跳到指定秒数,截播放器画面;同时存官方封面图(_cover.jpg)。截不到画面时用封面。
截完自动去掉四周空白(用了 --el/--box/--scale 时不裁,保证 boxes 坐标准确)。同名 .json 记来源、时间、图片尺寸 size、boxes。
登记进素材库用 `hz asset add`。
"""
import os, sys, json, re, time, argparse, tempfile, urllib.request, urllib.parse, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

def chrome_shot(target, out, size="1600x1000", wait=8, profile=None):
    w, h = size.lower().split("x")
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio", f"--window-size={w},{h}",
           f"--virtual-time-budget={int(wait * 1000)}", "--autoplay-policy=no-user-gesture-required", f"--screenshot={out}", target]
    if profile: cmd.insert(1, f"--user-data-dir={profile}")
    px = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if px: cmd[1:1] = [f"--proxy-server={px}", "--proxy-bypass-list=127.0.0.1;localhost;<local>"]   # 跟随本机代理
    subprocess.run(cmd, capture_output=True, timeout=wait + 60)
    if not os.path.exists(out) or os.path.getsize(out) < 2000: raise SystemExit(f"截图失败: {target}")

def _proxy():
    """跟随本机代理:环境变量优先,其次 HZ_PROXY(默认 127.0.0.1:7897);代理没开就直连。"""
    import socket
    px = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
          or os.environ.get("HZ_PROXY", "127.0.0.1:7897"))
    try:
        host, port = px.split("//")[-1].rstrip("/").rsplit(":", 1); socket.create_connection((host, int(port)), 1).close(); return px
    except Exception: return None

BOXJS = r"""((a) => {
  const find = (q) => {
    if (q.startsWith('@')) {   // 文字定位:先比「整段就是这几个字」>「以它开头」>「包含它」,同级取面积最小、看得见的
      const up = (q.match(/\^+$/) || [''])[0].length, s = q.slice(1, q.length - up); let best = null, bk = [9, 1e18];
      for (const e of document.body.querySelectorAll('*')) { const tx = (e.textContent || '').trim(); if (!tx.includes(s)) continue;
        const r = e.getBoundingClientRect(), cs = getComputedStyle(e); if (r.width < 2 || r.height < 2 || cs.visibility === 'hidden' || +cs.opacity < 0.1) continue;
        const k = [tx === s ? 0 : tx.startsWith(s) ? 1 : 2, r.width * r.height]; if (k[0] < bk[0] || (k[0] === bk[0] && k[1] < bk[1])) { bk = k; best = e; } }
      let e = best && up ? best.closest('a,button,[role=button],li,label') || best.parentElement : best;
      for (let k = 1; e && k < up; k++) e = e.parentElement;   // 每多一个 ^ 再往外取一层
      return e; }
    return document.querySelector(q);
  };
  const R = (e) => { const r = e.getBoundingClientRect(); return [r.left + scrollX, r.top + scrollY, r.width, r.height]; };
  let clip;
  if (a.el) { const e = find(a.el); if (!e) return { err: '找不到 --el ' + a.el }; const r = R(e); clip = [r[0] - a.pad, r[1] - a.pad, r[2] + 2 * a.pad, r[3] + 2 * a.pad]; }
  else if (a.full) clip = [0, 0, document.documentElement.scrollWidth, document.documentElement.scrollHeight];
  else clip = [scrollX, scrollY, innerWidth, innerHeight];
  clip[0] = Math.max(0, clip[0]); clip[1] = Math.max(0, clip[1]);
  const boxes = {}, miss = [];
  for (const [k, q] of Object.entries(a.boxes)) { const e = find(q); if (!e) { miss.push(k); continue; } const r = R(e);
    boxes[k] = [(r[0] - clip[0]) / clip[2], (r[1] - clip[1]) / clip[3], r[2] / clip[2], r[3] / clip[3]].map((v) => +v.toFixed(4)); }
  return { clip, boxes, miss };
})(%s)"""

def cdp_shot(url, out, size, wait, scale=1, el=None, boxes=None, full=False, pad=12, theme=None, hide=()):
    """用调试协议截图:可只截某个元素、按倍数清晰度截,并量出若干元素的位置(返回 boxes / miss / clip)。"""
    from _cdp import Browser
    w, h = (int(x) for x in size.lower().split("x"))
    b = Browser(w, h, proxy=_proxy())
    try:
        b.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=scale, mobile=False)
        if theme: b.call("Emulation.setEmulatedMedia", features=[dict(name="prefers-color-scheme", value=theme)])
        b.goto(url, timeout=wait + 60); time.sleep(wait)
        if hide: b.js("(() => { const s = document.createElement('style'); s.textContent = %s; document.head.appendChild(s); })()" % json.dumps(", ".join(hide) + "{display:none!important}"), False); time.sleep(0.5)
        r = b.js(BOXJS % json.dumps(dict(el=el, boxes=boxes or {}, full=full, pad=pad), ensure_ascii=False), False)
        if r.get("err"): raise SystemExit(r["err"])
        x, y, cw, ch = r["clip"]
        png = b.call("Page.captureScreenshot", format="png", captureBeyondViewport=True, clip=dict(x=x, y=y, width=cw, height=ch, scale=1))["data"]
        import base64; open(out, "wb").write(base64.b64decode(png))
    finally:
        b.close()
    if os.path.getsize(out) < 2000: raise SystemExit(f"截图失败: {url}")
    return r

def autocrop(path, pad=16, tol=10):
    import cv2, numpy as np
    im = cv2.imread(path); bg = im[2, 2].astype(int)
    m = (np.abs(im.astype(int) - bg).sum(2) > tol)
    ys, xs = np.where(m)
    if len(xs) == 0: return
    y0, y1, x0, x1 = max(0, ys.min() - pad), min(im.shape[0], ys.max() + pad), max(0, xs.min() - pad), min(im.shape[1], xs.max() + pad)
    cv2.imwrite(path, im[y0:y1, x0:x1])

def crop_component(path, fx, fy, tol=12, pad=0):
    """以 (fx,fy)(相对坐标)所在的非背景连通区域为准裁切,用来裁出播放器。"""
    import cv2, numpy as np
    im = cv2.imread(path); h, w = im.shape[:2]; bg = im[h - 3, w // 2].astype(int)
    m = (np.abs(im.astype(int) - bg).sum(2) > tol).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    k = lab[int(h * fy), int(w * fx)]
    if k == 0: return False
    x, y, ww, hh = stats[k][:4]; cv2.imwrite(path, im[max(0, y - pad):y + hh + pad, max(0, x - pad):x + ww + pad]); return True

def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()

ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["url", "tweet", "yt"]); ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--size", default="1600x1000"); ap.add_argument("--wait", type=float, default=8); ap.add_argument("--full", action="store_true")
ap.add_argument("--theme"); ap.add_argument("--t", type=float, default=30)
ap.add_argument("--scale", type=float, default=1); ap.add_argument("--el"); ap.add_argument("--pad", type=int, default=12)
ap.add_argument("--box", action="append", default=[], help="名字=选择器(或 @文字),可写多个")
ap.add_argument("--hide", action="append", default=[], help="截图前隐藏的元素(CSS 选择器),可写多个")
a = ap.parse_args(); out = os.path.abspath(a.out); os.makedirs(os.path.dirname(out), exist_ok=True)
meta = dict(mode=a.mode, source=a.src, captured=time.strftime("%Y-%m-%d %H:%M"))

if a.mode == "url" and (a.el or a.box or a.scale != 1 or a.theme or a.hide):
    bx = dict(x.split("=", 1) for x in a.box)
    r = cdp_shot(a.src, out, a.size, a.wait, a.scale, a.el, bx, a.full, a.pad, a.theme, a.hide)
    meta.update(scale=a.scale, el=a.el, theme=a.theme, boxes=r["boxes"], clip=[round(v, 1) for v in r["clip"]])
    if r["miss"]: meta["boxes_missing"] = r["miss"]; print("⚠️ 这些框选区域没找到:", "、".join(r["miss"]), file=sys.stderr)
    outside = [k for k, (x, y, w_, h_) in r["boxes"].items() if x < -0.01 or y < -0.01 or x + w_ > 1.01 or y + h_ > 1.01]
    if outside: meta["boxes_outside"] = outside; print("⚠️ 这些框选区域在截图范围外(换 --el 或 --full 再截):", "、".join(outside), file=sys.stderr)

elif a.mode == "url":
    chrome_shot(a.src, out, a.size, a.wait)

elif a.mode == "tweet":
    m = re.search(r"status(?:es)?/(\d+)", a.src)
    if not m: raise SystemExit("推文网址里找不到编号(应形如 x.com/用户/status/数字)")
    tid = m.group(1)
    try:
        emb = json.loads(get("https://publish.twitter.com/oembed?" + urllib.parse.urlencode(dict(url=f"https://twitter.com/i/status/{tid}", dnt="true"))))
        meta.update(author=emb.get("author_name"), author_url=emb.get("author_url"))
    except Exception: pass
    chrome_shot(f"https://platform.twitter.com/embed/Tweet.html?id={tid}&theme={a.theme or 'dark'}&dnt=true&lang=zh-cn", out, "600x1400", max(a.wait, 22))
    autocrop(out, pad=0)
    meta.update(tweet_id=tid)

elif a.mode == "yt":
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})", a.src); vid = m.group(1) if m else a.src.strip()
    thumb = out[:-4] + "_cover.jpg"
    for q in ("maxresdefault", "hqdefault"):
        try: open(thumb, "wb").write(get(f"https://i.ytimg.com/vi/{vid}/{q}.jpg")); break
        except Exception: continue
    try:
        o = json.loads(get("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}")))
        meta.update(title=o.get("title"), author=o.get("author_name"), author_url=o.get("author_url"))
    except Exception: pass
    page = out[:-4] + "_page.png"; frame_ok = False
    try:
        chrome_shot(f"https://www.youtube.com/watch?v={vid}&t={int(a.t)}s", page, "1600x1000", max(a.wait, 20))
        import shutil; shutil.copy(page, out); frame_ok = crop_component(out, 0.2, 0.3)
        if frame_ok:
            import cv2; im = cv2.imread(out); frame_ok = im.shape[1] > 600 and 1.4 < im.shape[1] / im.shape[0] < 2.0 and im.std() > 18
    except SystemExit: pass
    if not frame_ok:
        import shutil; shutil.copy(thumb, out); meta["note"] = "未能截到指定秒数的画面,已用官方封面图(整页截图见 _page.png)"
    meta.update(video_id=vid, t=a.t, cover=thumb)

try:
    import cv2; _im = cv2.imread(out); meta["size"] = [int(_im.shape[1]), int(_im.shape[0])]
except Exception: pass
json.dump(meta, open(out[:-4] + ".json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(dict(out=out, **meta), ensure_ascii=False))
