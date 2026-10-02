"""텍스처 글자 교체(인덱스 공간).
원본 글자 영역의 구조(바깥에서부터 거리별 테두리 인덱스, 안쪽 채움의 세로 그라데이션)를 재서
같은 구조로 한글을 그린다. 팔레트는 건드리지 않는다(게임이 다른 CLUT 를 쓰는 경우도 안전)."""
import os, sys, struct, collections
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swz, tex
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
FONTS = {'heavy': 'NanumSquareNeo-eHv.ttf', 'xbold': 'NanumSquareNeo-dEb.ttf', 'bold': 'NanumSquareNeo-cBd.ttf', 'regular': 'NanumSquareNeo-bRg.ttf'}

def load(b, o):
    w, h, psm = tex.parse(b, o)
    sw = bool(b[o + 0x17] & 0x80)
    d = o + 0x40
    if psm == 0x13:
        idx = swz.unswizzle8(b[d:d + w * h], w, h) if sw else np.frombuffer(b[d:d + w * h], np.uint8).reshape(h, w)
        po = tex.pal_off(b, o); pal = tex.csm1(np.frombuffer(b[po:po + 1024].ljust(1024, bytes(1)), np.uint8).reshape(256, 4).copy())
    else:
        raw = np.frombuffer(b[d:d + w * h // 2], np.uint8)
        idx = swz.unswizzle4(b[d:d + w * h // 2], w, h) if sw else np.stack([raw & 15, raw >> 4], 1).reshape(h, w)
        po = tex.pal_off(b, o); pal = np.frombuffer(b[po:po + 64].ljust(64, bytes(1)), np.uint8).reshape(16, 4).copy()
    return np.array(idx, np.uint8), pal, dict(w=w, h=h, psm=psm, sw=sw)

def store(b, o, idx):
    """bytearray b 의 텍스처 픽셀을 idx 로 교체."""
    w, h, psm = tex.parse(b, o)
    sw = bool(b[o + 0x17] & 0x80)
    d = o + 0x40
    if psm == 0x13:
        data = swz.swizzle8(idx) if sw else idx.astype(np.uint8).tobytes()
    else:
        data = swz.swizzle4(idx) if sw else ((idx[:, 0::2] & 15) | ((idx[:, 1::2] & 15) << 4)).astype(np.uint8).tobytes()
    b[d:d + len(data)] = data

def background(idx, pal):
    """투명(알파 최소) 인덱스 중 가장 많이 쓰인 것."""
    cnt = np.bincount(idx.ravel(), minlength=len(pal))
    a = pal[:, 3].astype(int)
    cands = [i for i in range(len(pal)) if a[i] == a.min()]
    return max(cands, key=lambda i: cnt[i]) if cands else int(cnt.argmax())

def segment(idx, bg, gx=6, gy=2, minpix=12):
    """글자 덩어리 영역(가로로 가까운 글자끼리 합침): [(x0,y0,x1,y1), ...] (x1,y1 제외)."""
    m = idx != bg
    dm = ndimage.binary_dilation(m, structure=np.ones((2 * gy + 1, 2 * gx + 1), bool))
    lab, n = ndimage.label(dm)
    boxes = []
    for sl in ndimage.find_objects(lab):
        ys, xs = sl
        sub = m[sl]
        if sub.sum() < minpix: continue
        yy, xx = np.nonzero(sub)
        boxes.append((xs.start + xx.min(), ys.start + yy.min(), xs.start + xx.max() + 1, ys.start + yy.max() + 1))
    boxes.sort(key=lambda b: (b[1] // 8, b[0]))
    return boxes

def _dout(mask):
    """마스크 안 각 픽셀의 바깥(배경)까지 유클리드 거리."""
    return ndimage.distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1]

def style_of(idx, box, bg, K=10, D=8):
    """(바깥 거리, 세로 위치) → 인덱스 표. t = 테두리 두께(안쪽 채움 시작 거리)."""
    x0, y0, x1, y1 = box
    sub = idx[y0:y1, x0:x1]
    m = sub != bg
    d = _dout(m)
    h = y1 - y0
    ys = np.nonzero(m.any(1))[0]
    g0, g1 = (ys.min(), ys.max() + 1) if len(ys) else (0, h)
    tab = {}
    for di in range(1, D + 1):
        band = m & (d > di - 1) & (d <= di)
        for k in range(K):
            r0 = g0 + int(k * (g1 - g0) / K); r1 = max(r0 + 1, g0 + int((k + 1) * (g1 - g0) / K))
            v = sub[r0:r1][band[r0:r1]]
            if len(v): tab[(di, k)] = collections.Counter(v.tolist()).most_common(1)[0][0]
    # 띠별 대표 인덱스로 테두리 두께 추정: 가장 깊은 띠 인덱스(채움)와 같은 첫 거리
    rep = []
    for di in range(1, D + 1):
        v = sub[m & (d > di - 1) & (d <= di)]
        rep.append(collections.Counter(v.tolist()).most_common(1)[0][0] if len(v) else None)
    rep = [r for r in rep if r is not None]
    core = collections.Counter(sub[m & (d > 2)].tolist()).most_common(1)[0][0] if (m & (d > 2)).any() else (rep[-1] if rep else 0)
    t = 0
    for r in rep:
        if r == core: break
        t += 1
    t = min(t, 5)
    return dict(tab=tab, t=t, K=K, D=D, core=core)

def render_mask(text, w, h, weight='heavy', pad=0, maxsq=0.70):
    """w×h 칸 안(여백 pad)에 들어가는 한글 마스크(가운데 정렬, 넘치면 가로 압축 후 축소)."""
    font_path = os.path.join(ROOT, FONTS[weight])
    iw, ih = max(1, w - 2 * pad), max(1, h - 2 * pad)
    S = 4
    f = ImageFont.truetype(font_path, max(8, int(ih * S * 1.25)))
    im = Image.new('L', (1, 1)); dr = ImageDraw.Draw(im)
    x0, y0, x1, y1 = dr.textbbox((0, 0), text, font=f)
    img = Image.new('L', (x1 - x0 + 4, y1 - y0 + 4), 0)
    ImageDraw.Draw(img).text((2 - x0, 2 - y0), text, font=f, fill=255)
    tw, th = img.size
    # 높이를 ih 에 맞춤
    sc = ih / th
    nw, nh = tw * sc, th * sc
    if nw > iw:
        sx = iw / nw
        if sx >= maxsq: nw = iw
        else:
            nw = nw * maxsq; s2 = iw / nw; nw, nh = iw, nh * s2
    nw, nh = max(1, int(round(nw))), max(1, int(round(nh)))
    small = np.asarray(img.resize((nw, nh), Image.LANCZOS), np.float32) / 255
    out = np.zeros((h, w), np.float32)
    ox, oy = (w - nw) // 2, (h - nh) // 2
    out[oy:oy + nh, ox:ox + nw] = small
    return out > 0.45

def paint(idx, box, text, st, bg, weight='heavy'):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    t = st['t']
    glyph = render_mask(text, w, h, weight, pad=t)
    if t:
        dg = ndimage.distance_transform_edt(~glyph)
        full = glyph | (dg <= t + 0.2)
    else:
        full = glyph
    d = _dout(full)
    ys = np.nonzero(full.any(1))[0]
    g0, g1 = (ys.min(), ys.max() + 1) if len(ys) else (0, h)
    area = np.zeros((h, w), np.uint8) + bg
    K, D, tab = st['K'], st['D'], st['tab']
    yy, xx = np.nonzero(full)
    for y, x in zip(yy, xx):
        di = min(D, max(1, int(np.ceil(d[y, x]))))
        k = min(K - 1, max(0, int((y - g0) * K / max(1, g1 - g0))))
        v = tab.get((di, k))
        if v is None:
            for dd in range(di, 0, -1):
                v = tab.get((dd, k))
                if v is not None: break
        area[y, x] = st['core'] if v is None else v
    idx[y0:y1, x0:x1] = area
    return idx

def preview(idx, pal, path, scale=2):
    rgba = pal[idx].copy(); rgba[..., 3] = 255
    Image.fromarray(rgba, 'RGBA').resize((idx.shape[1] * scale, idx.shape[0] * scale), Image.NEAREST).save(path)

# ---------------- RGBA 공간 편집 (실제 팔레트 색 기준) ----------------
def rgba_of(idx, pal):
    return pal[idx].astype(np.float32)

def panel_bg(idx, pal, box, bg, force=False):
    """상자 테두리가 불투명한 판(버튼) 위면, 줄마다 판 색 인덱스 배열(h,w) 을 돌려준다. 아니면 None."""
    x0, y0, x1, y1 = box
    sub = idx[y0:y1, x0:x1]; h, w = sub.shape
    if h < 3 or w < 3: return None
    ring = np.concatenate([sub[0], sub[-1], sub[:, 0], sub[:, -1]])
    amin = 8 if force else 96
    if np.mean((ring != bg) & (pal[ring, 3] >= amin)) < 0.8: return None
    allc = np.bincount(ring, minlength=len(pal)).argmax()
    rows = np.empty(h, np.int64)
    W = idx.shape[1]
    for y in range(h):
        row = np.concatenate([idx[y0 + y, max(0, x0 - 6):x0], idx[y0 + y, x1:min(W, x1 + 6)]])
        row = row[(row != bg) & (pal[row, 3] >= amin)]
        rows[y] = np.bincount(row, minlength=len(pal)).argmax() if len(row) else allc
    return np.repeat(rows[:, None], w, 1)

def photo_bg(idx, pal, box, bg):
    """사진 같은 불규칙 배경 위 글자: 상자 안을 테두리 픽셀로 메운(inpaint) RGBA 배경 (h,w,4). 판이 균일하면 None."""
    import cv2
    x0, y0, x1, y1 = box
    H, W = idx.shape
    xa, ya, xb, yb = max(0, x0 - 2), max(0, y0 - 2), min(W, x1 + 2), min(H, y1 + 2)
    big = pal[idx[ya:yb, xa:xb]].astype(np.float32)
    ring = np.ones(big.shape[:2], bool); ring[y0 - ya:y1 - ya, x0 - xa:x1 - xa] = False
    op = big[ring][:, 3] >= 96
    if ring.sum() < 8 or np.mean(op) < 0.5: return None
    if big[ring][op][:, :3].std(0).mean() < 22: return None
    img = np.clip(big[..., :3], 0, 255).astype(np.uint8)
    m = (~ring).astype(np.uint8) * 255
    out = cv2.inpaint(img, m, 3, cv2.INPAINT_TELEA).astype(np.float32)
    al = cv2.inpaint(np.clip(big[..., 3], 0, 255).astype(np.uint8), m, 3, cv2.INPAINT_TELEA).astype(np.float32)[..., None]
    return np.concatenate([out, al], -1)[y0 - ya:y1 - ya, x0 - xa:x1 - xa]

def _bgmask(sub, pal, bg):
    """배경(투명 또는 판 색) 여부."""
    if np.ndim(bg) == 0: return sub == bg
    if np.ndim(bg) == 3:
        return np.abs(pal[sub].astype(np.float32)[..., :3] - bg[..., :3]).sum(-1) < 40
    d = np.abs(pal[sub].astype(np.float32)[..., :3] - pal[bg].astype(np.float32)[..., :3]).sum(-1)
    return d < 40

def style_rgba(idx, pal, box, bg, K=5, D=8):
    """거리 띠(1..D)별 색, 세로 구간(K)별 채움 색, 테두리 두께 t. bg: 투명 인덱스 또는 판 색 배열."""
    x0, y0, x1, y1 = box
    sub = idx[y0:y1, x0:x1]
    col = pal[sub].astype(np.float32)
    m = (~_bgmask(sub, pal, bg)) & (col[..., 3] > 8)
    d = _dout(m)
    opaque = m & (col[..., 3] >= 96)
    ys = np.nonzero((opaque if opaque.any() else m).any(1))[0]
    h = y1 - y0
    g0, g1 = (ys.min(), ys.max() + 1) if len(ys) else (0, h)
    band = []
    for di in range(1, D + 1):
        sel = m & (d > di - 1) & (d <= di)
        band.append(np.median(col[sel], 0) if sel.any() else None)
    band = [b_ for b_ in band if b_ is not None]
    if not band: return None
    dmax = d[m].max() if m.any() else 1
    inner = m & (d >= max(1.5, dmax * 0.6))
    cin = np.median(col[inner], 0) if inner.any() else band[-1]
    t = 0
    for b_ in band:
        if np.abs(b_[:3] - cin[:3]).sum() < 60: break
        t += 1
    t = max(1, min(t, int(round((y1 - y0) * 0.06)) + 1, 4)) if band else 0
    fill = []
    fmask = m & (d > t) & (col[..., 3] >= 96)
    deep = fmask & (d > t + 1.5)
    if deep.sum() >= max(20, fmask.sum() * 0.2): fmask = deep
    if t and fmask.any():
        # 테두리·그림자 색보다 채움 대표색(cin)에 가까운 픽셀만
        bands_arr = np.array(band[:t], np.float32)
        dc = np.abs(col[..., :3] - cin[:3]).sum(-1)
        db = np.min(np.abs(col[..., None, :3] - bands_arr[None, None, :, :3]).sum(-1), -1)
        fmask = fmask & (db > 45)
    rows = []
    for k in range(K):
        r0 = g0 + int(k * (g1 - g0) / K); r1 = max(r0 + 1, g0 + int((k + 1) * (g1 - g0) / K))
        sel = fmask[r0:r1]
        rows.append(np.median(col[r0:r1][sel], 0) if sel.sum() >= 3 else None)
    good = [i for i, r in enumerate(rows) if r is not None]
    for k in range(K):
        if rows[k] is None:
            rows[k] = rows[min(good, key=lambda i: abs(i - k))] if good else cin
    # 그라데이션 없이 대표색 1가지: 채움 픽셀 전체의 중앙값(주된 색)
    rep = np.median(col[fmask], 0) if fmask.sum() >= 3 else cin
    fill = [rep] * K
    return dict(band=[b_.tolist() for b_ in band[:max(t, 1)]], fill=[f.tolist() for f in fill], t=t, K=K)

def quantize(rgb, pal, used=None):
    """RGBA 배열 → 팔레트 인덱스(가장 가까운 색). used: 후보 인덱스 제한."""
    P = pal.astype(np.float32)
    cand = np.arange(len(P)) if used is None else np.array(sorted(used))
    Pc = P[cand]
    flat = rgb.reshape(-1, 4)
    w = np.array([1, 1, 1, 2.0], np.float32)
    out = np.empty(len(flat), np.int64)
    for s in range(0, len(flat), 4096):
        blk = flat[s:s + 4096]
        dd = (((blk[:, None, :] - Pc[None, :, :]) ** 2) * w).sum(-1)
        out[s:s + 4096] = cand[dd.argmin(1)]
    return out.reshape(rgb.shape[:2])

def paint_rgba(idx, pal, box, text, st, bg, weight='heavy', S=4, align='center'):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    t = st['t']
    # 슈퍼샘플 글자 마스크
    glyph = render_mask_ss(text, w, h, weight, pad=max(1, int(np.ceil(t * 0.6))), S=S, align=align)
    gb = glyph > 0.5
    if t:
        dg = ndimage.distance_transform_edt(~gb)
        comp = gb | (dg <= t * S)
    else:
        comp = gb
    cov = comp.reshape(h, S, w, S).mean((1, 3))                     # 전체 덮임
    fcov = gb.reshape(h, S, w, S).mean((1, 3))                       # 채움 덮임
    dcomp = ndimage.distance_transform_edt(np.pad(comp, 1))[1:-1, 1:-1] / S
    dpx = dcomp.reshape(h, S, w, S).mean((1, 3))
    ys = np.nonzero(cov.max(1) > 0)[0]
    g0, g1 = (ys.min(), ys.max() + 1) if len(ys) else (0, h)
    K = st['K']; band = np.array(st['band'], np.float32); fill = np.array(st['fill'], np.float32)
    yy = np.arange(h)
    krow = np.clip(((yy - g0) * K) // max(1, g1 - g0), 0, K - 1)
    fc = fill[krow][:, None, :].repeat(w, 1)                          # (h,w,4)
    if t:
        bi = np.clip(np.ceil(dpx).astype(int) - 1, 0, len(band) - 1)
        bc = band[bi]
        f = fcov[..., None]
        oc = bc * (1 - f) + fc * f
        colr = np.where((fcov < 0.5)[..., None], oc, fc)
    else:
        colr = fc.copy()
    region = idx[y0:y1, x0:x1]
    if np.ndim(bg) == 0:
        colr[..., 3] = colr[..., 3] * np.clip(cov, 0, 1)
        colr[cov <= 0.02] = 0
        out = colr
        used = set(np.unique(region).tolist()) | {bg}
        q = quantize(out, pal, used if len(used) >= 4 else None)
        q[out[..., 3] < 4] = bg
    else:
        # 판 위: 판 색 위에 합성, 글자 밖은 판 색으로 메움
        pc = bg if np.ndim(bg) == 3 else pal[bg].astype(np.float32); a = np.clip(cov, 0, 1)[..., None]
        out = colr * a + pc * (1 - a); out[..., 3] = np.maximum(pc[..., 3], np.minimum(colr[..., 3], 128) * a[..., 0])
        if np.ndim(bg) == 3:
            q = quantize(out, pal)
        else:
            used = set(np.unique(region).tolist()) | set(np.unique(bg).tolist())
            q = quantize(out, pal, used if len(used) >= 4 else None)
            q[cov <= 0.02] = bg[cov <= 0.02]
    region[:] = q
    return idx

def render_mask_ss(text, w, h, weight='heavy', pad=0, S=4, maxsq=0.70, align='center'):
    """슈퍼샘플(S배) 덮임 마스크 (h*S, w*S)."""
    font_path = os.path.join(ROOT, FONTS[weight])
    W, H, P = w * S, h * S, pad * S
    iw, ih = max(1, W - 2 * P), max(1, H - 2 * P)
    f = ImageFont.truetype(font_path, max(8, int(ih * 1.25)))
    im = Image.new('L', (1, 1)); dr = ImageDraw.Draw(im)
    x0, y0, x1, y1 = dr.textbbox((0, 0), text, font=f)
    img = Image.new('L', (x1 - x0 + 4, y1 - y0 + 4), 0)
    ImageDraw.Draw(img).text((2 - x0, 2 - y0), text, font=f, fill=255)
    tw, th = img.size
    sc = ih / th
    nw, nh = tw * sc, th * sc
    if nw > iw:
        if iw / nw >= maxsq: nw = iw
        else:
            nw = nw * maxsq; s2 = iw / nw; nw, nh = iw, nh * s2
    nw, nh = max(1, int(round(nw))), max(1, int(round(nh)))
    small = np.asarray(img.resize((nw, nh), Image.LANCZOS), np.float32) / 255
    out = np.zeros((H, W), np.float32)
    ox, oy = ((W - nw) // 2 if align == 'center' else P), (H - nh) // 2
    out[oy:oy + nh, ox:ox + nw] = small
    return out

def override_style(st, it):
    """명세 항목의 fill / outline / t 로 스타일 덮어쓰기 (사진 위 글자 등)."""
    if st is None: return st
    if 'fill' in it: st['fill'] = [list(it['fill'][:3]) + [128]] * st['K']
    if 't' in it: st['t'] = int(it['t'])
    if 'outline' in it:
        st['t'] = max(st['t'], 1); st['band'] = [list(it['outline'][:3]) + [128]] * st['t']
    return st
