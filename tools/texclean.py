"""그림 글자 깔끔하게 다시 그리기 (통일된 규칙).
1) 원래 글자를 상자 전체에서 완전히 지움: 투명 바탕이면 투명으로, 판·그라데이션·사진이면 주변 픽셀로 메움(inpaint).
2) 글자 크기: 원래 글자의 실제 높이에 맞춤. 가로는 최대 78%까지만 눌러 담고, 넘치면 글자 크기를 줄임.
3) 색: 단색 채움 + 단색 테두리. 채움은 원래 글자 속 대표색, 테두리는 원래 바깥 테두리색.
   바탕과 명도 차가 작으면 채움을 밝게/어둡게 밀어 가독성 확보. 테두리가 채움과 비슷하면 반대 명도로 바꿈.
항목 옵션: fill, outline, t(테두리 두께), weight, align, mode('clear'=지우기만)."""
import os, sys, colorsys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texedit
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
FONTS = texedit.FONTS

def lum(c): return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

def _rgba(idx, pal): return pal[idx].astype(np.float32)

def analyse(idx, pal, box, bgi):
    """원래 글자: 불투명 마스크, 실제 글자 높이, 채움색, 테두리색, 두께, 바탕 종류."""
    x0, y0, x1, y1 = box
    H, W = idx.shape
    rg = _rgba(idx, pal)
    xa, ya, xb, yb = max(0, x0 - 3), max(0, y0 - 3), min(W, x1 + 3), min(H, y1 + 3)
    ring = np.ones((yb - ya, xb - xa), bool); ring[y0 - ya:y1 - ya, x0 - xa:x1 - xa] = False
    ringpx = rg[ya:yb, xa:xb][ring]
    opaque_ring = (ringpx[:, 3] >= 64).mean() if len(ringpx) else 0
    sub = rg[y0:y1, x0:x1]
    inset = False
    # 옆 띠(상자 좌우 안팎 3px)의 줄별 색으로 바탕 추정
    xl0, xl1 = max(0, x0 - 3), min(W, x0 + 2); xr0, xr1 = max(0, x1 - 2), min(W, x1 + 3)
    side = np.concatenate([rg[y0:y1, xl0:xl1], rg[y0:y1, xr0:xr1]], 1)
    sop = side[..., 3] >= 64
    transp = (ringpx[:, 3] < 8).mean() if len(ringpx) else 1
    kind = 'alpha' if (opaque_ring < 0.5 or transp > 0.08) else 'panel'
    flatbg = False; rowc = None
    if kind == 'alpha':
        m = sub[..., 3] > 24
        bgcol = None
    else:
        rows = []; sds = []
        full = rg[y0:y1, max(0, x0 - 3):min(W, x1 + 3)]
        fop = full[..., 3] >= 64
        for yy in range(full.shape[0]):
            r = full[yy][fop[yy]]
            if len(r) >= 4:
                med = np.median(r, 0)
                # 글자 픽셀(중앙값과 크게 다른 것) 빼고 다시
                k = np.abs(r[:, :3] - med[:3]).sum(1) < 60
                rows.append(np.median(r[k], 0) if k.sum() >= 3 else med)
                if k.sum() >= 3: sds.append(r[k][:, :3].std(0).mean())
            else: rows.append(None)
        good = [i for i, r in enumerate(rows) if r is not None]
        for i in range(len(rows)):
            if rows[i] is None: rows[i] = rows[min(good, key=lambda g: abs(g - i))] if good else np.array([128, 128, 128, 128.])
        rowc = np.array(rows, np.float32)
        spread = float(np.median(sds)) if sds else 99
        flatbg = spread < 16
        if pal[bgi][3] >= 64:
            # 텍스처 전체 바탕이 불투명 단색(검은 판 등): 그 색 그대로
            flatbg = True; rowc = np.repeat(pal[bgi][None].astype(np.float32), sub.shape[0], 0)
        if flatbg:
            bgimg = np.repeat(rowc[:, None, :], sub.shape[1], 1)
        else:
            img = np.clip(rg[ya:yb, xa:xb], 0, 255).astype(np.uint8)
            mask = (~ring).astype(np.uint8) * 255
            rec = np.dstack([cv2.inpaint(np.ascontiguousarray(img[..., :3]), mask, 4, cv2.INPAINT_TELEA),
                             cv2.inpaint(np.ascontiguousarray(img[..., 3]), mask, 4, cv2.INPAINT_TELEA)]).astype(np.float32)
            bgimg = rec[y0 - ya:y1 - ya, x0 - xa:x1 - xa]
        bgimg[..., 3] = np.where(sub[..., 3] >= 64, np.maximum(bgimg[..., 3], 100), bgimg[..., 3])
        d = np.abs(sub[..., :3] - bgimg[..., :3]).sum(-1)
        m = d > 32
        # 상자 좌우 가장자리에 붙은 덩어리(버튼 테두리·끝 장식)는 글자가 아님
        lab, n = ndimage.label(m)
        hh, ww = m.shape
        for k in range(1, n + 1):
            ys_, xs_ = np.nonzero(lab == k)
            near = ((xs_ <= 3) | (xs_ >= ww - 4)).mean()
            if near > 0.5 and (xs_.min() == 0 or xs_.max() == ww - 1): m[lab == k] = False
        bgcol = np.median(bgimg.reshape(-1, 4), 0)
        # 글자(와 그 번짐) 픽셀만 복원 바탕으로, 나머지(테두리·아이콘)는 원본 유지
        if flatbg and m.any() and pal[bgi][3] < 64:
            # 2차: 글자 가로 구간 밖(좌우 여백, 상자 ±8px)의 줄별 색으로 다시
            cs = np.nonzero(ndimage.binary_dilation(m, iterations=2).any(0))[0]
            c0, c1 = x0 + cs.min(), x0 + cs.max() + 1
            L_ = rg[y0:y1, max(0, c0 - 8):c0]; R_ = rg[y0:y1, c1:min(W, c1 + 8)]
            mar = np.concatenate([L_, R_], 1)
            rows2 = []
            for yy in range(mar.shape[0]):
                r = mar[yy][mar[yy][:, 3] >= 64]
                rows2.append(np.median(r, 0) if len(r) >= 2 else bgimg[yy, 0])
            mstd = np.mean([np.std(mar[yy][mar[yy][:, 3] >= 64][:, :3], 0).mean() for yy in range(mar.shape[0]) if (mar[yy][:, 3] >= 64).sum() >= 3] or [99])
            bgimg = np.repeat(np.array(rows2, np.float32)[:, None, :], sub.shape[1], 1)
            bgimg[..., 3] = np.where(sub[..., 3] >= 64, np.maximum(bgimg[..., 3], 100), bgimg[..., 3])
        km = ndimage.binary_dilation(m | (np.abs(sub[..., :3] - bgimg[..., :3]).sum(-1) > 18), iterations=2)
        if m.any():
            # 원래 글자색(채움/테두리)에 가까운 픽셀은 상자 안 어디든 지움
            gc = sub[m][:, :3]
            far = np.abs(sub[..., :3] - bgimg[..., :3]).sum(-1) > 45
            km |= far & (sub[..., 3] >= 64) & ~bd_edge_mask(sub.shape[:2])
        if flatbg and m.any():
            km[:] = True                      # 단순 바탕: 상자 전체를 바탕으로
            km &= sub[..., 3] >= 64
        bgimg = np.where(km[..., None], bgimg, sub)
    if not m.any(): return None
    dist = ndimage.distance_transform_edt(m)
    ys = np.nonzero(m.any(1))[0]
    gh = ys.max() - ys.min() + 1
    dmax = dist.max()
    inner = m & (dist >= max(1.5, dmax * 0.55))
    P = sub[inner] if inner.sum() >= 3 else sub[m]
    mx = P[:, :3].max(1); mn = P[:, :3].min(1); sat = (mx - mn) / np.maximum(mx, 1)
    Pm = sub[m]; mxm = Pm[:, :3].max(1); mnm = Pm[:, :3].min(1); satm = (mxm - mnm) / np.maximum(mxm, 1)
    inner_achro = inner.sum() >= 3 and np.median(sat) < 0.2 and np.median(P[:, :3] @ np.array([0.299, 0.587, 0.114])) > 170
    if inner_achro:
        pass                           # 흰 글자(유채색 테두리): 안쪽 중앙값 유지
    elif (satm > 0.30).mean() > 0.06:   # 유채색 글자: 채도 높은 픽셀들의 중앙값
        P = Pm[satm > 0.30]
        L = P[:, :3] @ np.array([0.299, 0.587, 0.114])
        if kind == 'panel':
            bl = lum(np.median(bgimg.reshape(-1, 4), 0))
            P = P[np.abs(L - bl) >= np.median(np.abs(L - bl))]   # 바탕과 더 대비되는 쪽
        else:
            P = P[L >= np.median(L)]      # 그라데이션이면 밝은 쪽 절반
    fill = np.median(P, 0)
    edge = m & (dist <= 2) & (sub[..., 3] >= 96)
    outline = np.median(sub[edge], 0) if edge.any() else fill
    if not inner_achro and not ((satm > 0.30).mean() > 0.06):
        # 무채색 글자: 밝기 두 무리로 나눠 안쪽(거리 평균이 큰 쪽)=채움, 바깥=테두리
        L = sub[..., :3] @ np.array([0.299, 0.587, 0.114]); mm = m & (sub[..., 3] >= 96)
        if mm.sum() >= 10:
            thr = (L[mm].max() + L[mm].min()) / 2
            hi, lo = mm & (L >= thr), mm & (L < thr)
            if hi.sum() >= 3 and lo.sum() >= 3:
                a, b = (hi, lo) if dist[hi].mean() >= dist[lo].mean() else (lo, hi)
                fill = np.median(sub[a], 0); outline = np.median(sub[b], 0)
    t = 0
    if np.abs(outline[:3] - fill[:3]).sum() > 90:
        t = int(np.clip(round(dmax * 0.35), 1, 3))
    return dict(rowc=(rowc if kind == 'panel' and flatbg else None), kind=kind, gh=int(gh), gy=int(ys.min()), fill=fill, outline=outline, t=t, bg=bgcol,
                bgimg=(bgimg if kind == 'panel' else None))

def bd_edge_mask(shape):
    e = np.zeros(shape, bool); return e

def _contrast_fix(fill, ref, need=95):
    """fill 을 ref(바탕 또는 테두리) 와 명도 차 need 이상이 되도록 밝기 조정(색상 유지)."""
    f = np.array(fill[:3], np.float32) / 255
    h, l, s = colorsys.rgb_to_hls(*f)
    target_up = lum(ref) < 128
    for _ in range(40):
        if abs(lum(np.array(colorsys.hls_to_rgb(h, l, s)) * 255) - lum(ref)) >= need: break
        l = min(1, l + 0.03) if target_up else max(0, l - 0.03)
    r = np.array(colorsys.hls_to_rgb(h, l, s)) * 255
    return np.concatenate([r, [fill[3] if len(fill) > 3 else 128]])

def standard_fill(fill, ref):
    """색상은 유지, 채도·명도를 표준화: 유채색은 선명하게, 기준(테두리/바탕)과 반대 명도로."""
    r, g, b = [float(x) / 255 for x in fill[:3]]
    h, s_, v = colorsys.rgb_to_hsv(r, g, b)
    light_ref = lum(ref) > 140
    if s_ >= 0.22:
        s_ = max(s_, 0.8); v = 0.72 if light_ref else 1.0
    else:
        s_ = 0; v = 0.12 if light_ref else 1.0
    rr = np.array(colorsys.hsv_to_rgb(h, s_, v)) * 255
    return np.concatenate([rr, [128]]).astype(np.float32)

def glyph_mask(text, w, h, gh, weight, align, S=4, minsq=0.68):
    """슈퍼샘플 마스크: 글자 높이 gh(px) 에 맞추고 가로 최대 minsq 까지 압축, 넘치면 축소."""
    f = ImageFont.truetype(os.path.join(ROOT, FONTS.get(weight, FONTS['heavy'])), 200)
    im = Image.new('L', (1, 1)); dr = ImageDraw.Draw(im)
    bx = dr.textbbox((0, 0), text, font=f)
    img = Image.new('L', (bx[2] - bx[0] + 8, bx[3] - bx[1] + 8), 0)
    ImageDraw.Draw(img).text((4 - bx[0], 4 - bx[1]), text, font=f, fill=255)
    a = np.asarray(img)
    ys = np.nonzero(a.max(1) > 0)[0]; xs = np.nonzero(a.max(0) > 0)[0]
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    th, tw = a.shape
    sc = gh * S / th
    nh, nw = th * sc, tw * sc
    if nw > w * S:
        if w * S / nw >= minsq: nw = w * S
        else:
            nw *= minsq; k = w * S / nw; nw, nh = w * S, nh * k
    nh = min(nh, h * S)
    nw, nh = max(1, int(round(nw))), max(1, int(round(nh)))
    small = np.asarray(Image.fromarray(a).resize((nw, nh), Image.LANCZOS), np.float32) / 255
    return small

def shrink_to_text(orig, pal, box):
    """상자가 불투명 판 전체를 덮으면, 판 줄 색과 다른(글자) 영역으로 줄인다."""
    x0, y0, x1, y1 = box
    sub = pal[orig[y0:y1, x0:x1]].astype(np.float32)
    if (sub[..., 3] > 64).mean() < 0.93 or (y1 - y0) < 12: return box
    op = sub[..., 3] > 64
    med = np.array([np.median(sub[y][op[y]], 0) if op[y].any() else np.zeros(4) for y in range(sub.shape[0])])
    mx = sub[..., :3].max(-1); mn = sub[..., :3].min(-1)
    d = ((mx - mn) / np.maximum(mx, 1) > 0.4) | (np.abs(sub[..., :3] - med[:, None, :3]).sum(-1) > 160)
    d = ndimage.binary_opening(d, np.ones((2, 2)))
    # 가장자리(판 테두리) 제외
    cm = d.copy(); cm[:, :4] = cm[:, -4:] = False
    rows = np.nonzero(cm.sum(1) >= 2)[0]; cols = np.nonzero(cm.sum(0) >= 1)[0]
    if len(rows) < 4 or len(cols) < 4: return box
    return (max(x0 + 3, x0 + int(cols.min()) - 3), max(y0 + 2, y0 + int(rows.min()) - 3), min(x1 - 3, x0 + int(cols.max()) + 4), min(y1 - 2, y0 + int(rows.max()) + 4))

def grow_box(orig, pal, box, bgi):
    x0, y0, x1, y1 = box
    H, W = orig.shape
    rg = pal[orig].astype(np.float32)
    ring = np.concatenate([rg[y0:y1, max(0, x0 - 2):x0].reshape(-1, 4), rg[y0:y1, x1:min(W, x1 + 2)].reshape(-1, 4)])
    if len(ring) == 0 or (ring[:, 3] >= 64).mean() < 0.8: return box      # 투명 바탕이면 넓히지 않음
    # 좌우 이웃이 단순한 판일 때만(아이콘·그림 옆이면 넓히지 않음)
    for xs in (slice(max(0, x0 - 14), max(1, x0 - 6)), slice(min(W - 1, x1 + 6), min(W, x1 + 14))):
        nb = rg[y0:y1, xs].reshape(-1, 4)
        if len(nb) and (nb[:, 3] >= 64).mean() > 0.5 and nb[:, :3].std(0).mean() > 22: return box
    def col_has(x, a, b):
        c = rg[a:b, x]
        if pal[bgi][3] < 64 and (c[:, 3] < 8).all(): return False
        ref = np.median(rg[a:b, max(0, x0 - 12):max(1, x0 - 6)].reshape(-1, 4), 0) if x0 >= 7 else None
        return (c[:, 3] >= 24).any() if ref is None or ref[3] < 64 else (np.abs(c[:, :3] - ref[:3]).sum(1) > 70).any()
    for _ in range(8):
        if x0 > 0 and col_has(x0 - 1, y0, y1): x0 -= 1
        else: break
    for _ in range(8):
        if x1 < W and col_has(x1, y0, y1): x1 += 1
        else: break
    return (x0, y0, x1, y1)

def paint_plate(idx, pal, orig, box, text, it):
    """단순 판: 상자를 같은 줄 좌우 이웃 픽셀 색으로 메운 뒤, 지정 색으로 글자."""
    x0, y0, x1, y1 = box; H, W = orig.shape
    rg = pal[orig].astype(np.float32); h, w = y1 - y0, x1 - x0
    base = np.zeros((h, w, 4), np.float32)
    for yy in range(h):
        l = rg[y0 + yy, max(0, x0 - 4):x0]; r = rg[y0 + yy, x1:min(W, x1 + 4)]
        nb = np.concatenate([l, r]); nb = nb[nb[:, 3] >= 64] if len(nb) else nb
        if len(nb): 
            lc = np.median(l, 0) if len(l) else np.median(nb, 0); rc = np.median(r, 0) if len(r) else lc
            base[yy] = lc[None] * (1 - np.linspace(0, 1, w)[:, None]) + rc[None] * np.linspace(0, 1, w)[:, None]
        else: base[yy] = rg[y0 + yy, x0:x1]
    fill = np.array(list(it.get('fill', [255, 255, 255]))[:3] + [128], np.float32)
    outline = np.array(list(it.get('outline', [30, 30, 30]))[:3] + [128], np.float32)
    t = int(it.get('t', 1)); S = 4
    gh = int(it.get('gh', max(6, h - 2 * t - 2)))
    g = glyph_mask(text, max(1, w - 2 * t), h - 2 * t, gh, it.get('weight', 'heavy'), it.get('align', 'center'))
    M = np.zeros((h * S, w * S), np.float32); gh_, gw_ = g.shape
    oy = (h * S - gh_) // 2; al = it.get('align', 'center')
    ox = t * S if al == 'left' else (w * S - gw_) // 2
    M[oy:oy + gh_, ox:ox + gw_] = g[:h * S - oy, :w * S - ox]
    core = M > 0.5; comp = ndimage.distance_transform_edt(~core) <= t * S if t else core
    fc = core.reshape(h, S, w, S).mean((1, 3))[..., None]; cc = comp.reshape(h, S, w, S).mean((1, 3))[..., None]
    col = np.where(cc > 0, (outline * (cc - fc) + fill * fc) / np.maximum(cc, 1e-6), 0)
    out = col * cc + base * (1 - cc); out[..., 3] = np.maximum(base[..., 3], 128 * cc[..., 0])
    idx[y0:y1, x0:x1] = texedit.quantize(out, pal)

def paint_mask(idx, pal, orig, box, text, it):
    """밝기 마스크 텍스처(검은 바탕+흰 글자+회색 번짐, 게임이 색을 입힘): 상자를 바탕으로 지우고 흰 글자+번짐."""
    x0, y0, x1, y1 = box; H, W = orig.shape
    L = pal[:, :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114])
    if pal[:, 3].max() <= 64: L = pal[:, 3].astype(np.float32) * 4      # 알파 램프(색은 게임이 입힘)
    bgi = int(np.bincount(orig.ravel(), minlength=len(pal)).argmax())
    # 원래 글자 덩어리 전체(상자와 겹치는)를 지울 범위로
    m = L[orig] > L[bgi] + 6
    lab, n = ndimage.label(ndimage.binary_dilation(m, iterations=2))
    hit = set(np.unique(lab[y0:y1, x0:x1]).tolist()) - {0}
    kill = np.isin(lab, list(hit))
    idx[kill] = bgi
    if 'erase_box' in it:
        ex0, ey0, ex1, ey1 = it['erase_box']
        assert 0 <= ex0 < ex1 <= W and 0 <= ey0 < ey1 <= H
        idx[ey0:ey1, ex0:ex1] = bgi
    ys, xs = np.nonzero(kill)
    core0 = m & kill; cy = np.nonzero(core0.any(1))[0]
    gh0 = (cy.max() - cy.min() + 1) if len(cy) else (y1 - y0)
    if len(xs): x0, x1, y0, y1 = max(0, min(x0, xs.min())), min(W, max(x1, xs.max() + 1)), max(0, min(y0, ys.min())), min(H, max(y1, ys.max() + 1))
    h, w = y1 - y0, x1 - x0; S = 4
    g = glyph_mask(text, max(1, w - 6), h - 4, int(it.get('gh', max(8, gh0))), it.get('weight', 'heavy'), it.get('align', 'center'))
    M = np.zeros((h * S, w * S), np.float32); gh_, gw_ = g.shape
    oy = (h * S - gh_) // 2; ox = (w * S - gw_) // 2 if it.get('align', 'center') == 'center' else 3 * S
    M[oy:oy + gh_, ox:ox + gw_] = g[:h * S - oy, :w * S - ox]
    core = M > 0.5
    d = ndimage.distance_transform_edt(~core) / S
    fc = core.reshape(h, S, w, S).mean((1, 3))
    glow = np.clip(1 - d.reshape(h, S, w, S).mean((1, 3)) / float(it.get('glow', 3.0)), 0, 1) * 0.55
    val = np.maximum(fc, glow)
    target = L[bgi] + val * (L.max() - L[bgi])
    q = np.abs(L[None, None, :] - target[..., None]).argmin(-1)
    q[fc > 0.5] = int(L.argmax())
    reg = idx[y0:y1, x0:x1]
    reg[val > 0.02] = q[val > 0.02]

def paint_chip(idx, pal, orig, box, text, it):
    """원형 칩(포지션 표시): 원 안을 칩 색으로 다시 칠하고 흰 글자+짙은 테두리."""
    # 상자 주변에서 원의 중심(불투명 영역 내부 거리 최대점)과 반지름을 찾음
    A = pal[orig][..., 3] >= 64
    H, W = A.shape
    x0, y0, x1, y1 = box
    xa, ya, xb, yb = max(0, x0 - 4), max(0, y0 - 4), min(W, x1 + 4), min(H, y1 + 4)
    dt = ndimage.distance_transform_edt(np.pad(A[ya:yb, xa:xb], 1))[1:-1, 1:-1]
    wgt = dt.copy(); cy0, cx0 = (y0 + y1) / 2 - ya, (x0 + x1) / 2 - xa
    Yw, Xw = np.mgrid[0:dt.shape[0], 0:dt.shape[1]]; wgt -= 0.35 * np.sqrt((Yw - cy0) ** 2 + (Xw - cx0) ** 2)
    cyc, cxc = (np.array(np.unravel_index(wgt.argmax(), dt.shape)) + [ya, xa])
    R0 = dt.max()
    x0, y0 = int(max(0, cxc - R0 - 1)), int(max(0, cyc - R0 - 1)); x1, y1 = int(min(W, cxc + R0 + 2)), int(min(H, cyc + R0 + 2))
    rg = pal[orig[y0:y1, x0:x1]].astype(np.float32); h, w = rg.shape[:2]
    comp = None
    for it_ in (1, 2, 3, 4):
        er = ndimage.binary_erosion(A, iterations=it_)
        lab, _ = ndimage.label(er); k = lab[cyc, cxc]
        if not k: break
        cc_ = ndimage.binary_dilation(lab == k, iterations=it_) & A
        ys_, xs_ = np.nonzero(cc_)
        if (ys_.max() - ys_.min()) <= 1.5 * (xs_.max() - xs_.min() + 1) and (xs_.max() - xs_.min()) <= 1.5 * (ys_.max() - ys_.min() + 1):
            comp = cc_; break
    if comp is None: return
    ys_, xs_ = np.nonzero(comp)
    x0, y0, x1, y1 = xs_.min(), ys_.min(), xs_.max() + 1, ys_.max() + 1
    rg = pal[orig[y0:y1, x0:x1]].astype(np.float32); h, w = rg.shape[:2]
    op = comp[y0:y1, x0:x1]
    cyc, cxc = (y0 + y1 - 1) / 2, (x0 + x1 - 1) / 2; R0 = min(h, w) / 2
    if op.sum() < 20: return
    cy, cx, R = cyc - y0, cxc - x0, R0
    Y, X = np.mgrid[0:h, 0:w]; dd = np.sqrt((Y - cy) ** 2 + (X - cx) ** 2)
    ring = op & (dd > R - 4.5) & (dd < R - 2.0)
    P = rg[ring]; sat = (P[:, :3].max(1) - P[:, :3].min(1)) / np.maximum(P[:, :3].max(1), 1)
    body = np.median(P[sat >= np.median(sat)], 0) if len(P) else np.array([80, 80, 160, 128.])
    inner = ndimage.binary_erosion(op, iterations=2)
    base = rg.copy(); base[inner] = body; base[inner, 3] = 128
    bh, bs, bv = colorsys.rgb_to_hsv(*(np.clip(body[:3], 0, 255) / 255))
    outline = np.array(list(np.array(colorsys.hsv_to_rgb(bh, max(bs, 0.6), 0.3)) * 255) + [128], np.float32)
    fill = np.array([255, 255, 255, 128], np.float32)
    S = 4; t = 1; gh = int(it.get('gh', max(6, round(2 * R * 0.62))))
    g = glyph_mask(text, max(1, int(2 * R * 0.86)), h, gh, 'heavy', 'center')
    M = np.zeros((h * S, w * S), np.float32); gh_, gw_ = g.shape
    oy = int(round(cy * S + S / 2 - gh_ / 2)); ox = int(round(cx * S + S / 2 - gw_ / 2))
    oy = max(0, min(h * S - gh_, oy)); ox = max(0, min(w * S - gw_, ox))
    M[oy:oy + gh_, ox:ox + gw_] = g[:h * S - oy, :w * S - ox]
    core = M > 0.5; comp = ndimage.distance_transform_edt(~core) <= t * S
    fc = core.reshape(h, S, w, S).mean((1, 3))[..., None]; cc = comp.reshape(h, S, w, S).mean((1, 3))[..., None]
    col = np.where(cc > 0, (outline * (cc - fc) + fill * fc) / np.maximum(cc, 1e-6), 0)
    out = col * cc + base * (1 - cc); out[..., 3] = np.maximum(base[..., 3], 128 * cc[..., 0])
    q = texedit.quantize(out, pal)
    keep = ~op
    q[keep] = idx[y0:y1, x0:x1][keep]
    idx[y0:y1, x0:x1] = q

def paint_exact(idx, pal, orig, box, text, bgi, it):
    """Visually reviewed bounds: never grow into neighbouring atlas sprites.

    box clears all old ink; text_box independently positions the replacement.
    Palette and pixels outside box are preserved. RGB stays straight-alpha,
    avoiding the dark fringe caused by multiplying coverage into RGB twice.
    """
    x0, y0, x1, y1 = map(int, box)
    H, W = idx.shape
    assert 0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H, box
    h, w = y1 - y0, x1 - x0
    bgi = int(it.get('background_index', bgi))
    idx[y0:y1, x0:x1] = bgi
    if 'base_tile' in it:
        bx, by, bX, bY = it['base_tile']
        tile = Image.fromarray(orig[by:bY, bx:bX]).resize((w, h), Image.Resampling.NEAREST)
        idx[y0:y1, x0:x1] = np.asarray(tile)
    if not text.strip(): return
    tx0, ty0, tx1, ty1 = map(int, it.get('text_box', box))
    assert x0 <= tx0 < tx1 <= x1 and y0 <= ty0 < ty1 <= y1
    S = 4
    t = float(it.get('t', 1))
    pad = int(it.get('pad', int(np.ceil(t)) + 1))
    iw, ih = tx1 - tx0 - 2 * pad, ty1 - ty0 - 2 * pad
    assert iw > 0 and ih > 0, it
    g = glyph_mask(text, iw, ih, min(ih, it.get('gh', ih)),
                   it.get('weight', 'xbold'), it.get('align', 'center'), minsq=0.82)
    M = np.zeros((h * S, w * S), bool)
    gh, gw = g.shape
    ox = (tx0 - x0) * S + ((tx1 - tx0) * S - gw) // 2
    if it.get('align') == 'left': ox = (tx0 - x0 + pad) * S
    if it.get('align') == 'right': ox = (tx1 - x0 - pad) * S - gw
    oy = (ty0 - y0) * S + ((ty1 - ty0) * S - gh) // 2
    M[oy:oy + gh, ox:ox + gw] = g > 0.5
    outline_mask = ndimage.distance_transform_edt(~M) <= t * S if t else M
    fc = M.reshape(h, S, w, S).mean((1, 3))[..., None]
    cc = outline_mask.reshape(h, S, w, S).mean((1, 3))[..., None]
    if 'ink_ramp' in it:
        # Preserve CLUT roles, including palettes replaced by the game at runtime.
        # Each ramp runs from zero coverage to full coverage. Never quantize
        # against unrelated colours elsewhere in the texture's palette.
        ink = np.asarray(it['ink_ramp'], dtype=np.uint8)
        edge_ramp = np.asarray(it.get('edge_ramp', [bgi, int(ink[0])]), dtype=np.uint8)
        q = edge_ramp[np.rint(cc[..., 0] * (len(edge_ramp) - 1)).astype(int)]
        coverage = (fc[..., 0] / np.maximum(cc[..., 0], 1e-6)) ** float(it.get('ink_gamma', 1))
        inside = fc[..., 0] > 0
        q[inside] = ink[np.rint(coverage[inside] * (len(ink) - 1)).astype(int)]
        q[cc[..., 0] == 0] = idx[y0:y1, x0:x1][cc[..., 0] == 0]
        idx[y0:y1, x0:x1] = q
        return
    fill = np.array(it.get('fill', [255, 255, 255]), np.float32)[:3]
    edge = np.array(it.get('outline', [24, 40, 88]), np.float32)[:3]
    out = np.zeros((h, w, 4), np.float32)
    out[..., :3] = (fill * fc + edge * (cc - fc)) / np.maximum(cc, 1e-6)
    out[..., 3] = cc[..., 0] * 128
    if 'background_index' in it or 'base_tile' in it:
        base = pal[idx[y0:y1, x0:x1]].astype(np.float32)
        out[..., :3] = out[..., :3] * cc + base[..., :3] * (1 - cc)
        out[..., 3] = out[..., 3] + base[..., 3] * (1 - cc[..., 0])
    if 'palette_indices' in it:
        allowed = np.asarray(it['palette_indices'], dtype=np.uint8)
        q = allowed[texedit.quantize(out, pal[allowed])]
    else:
        q = texedit.quantize(out, pal)
    q[cc[..., 0] == 0] = idx[y0:y1, x0:x1][cc[..., 0] == 0]
    idx[y0:y1, x0:x1] = q


def paint(idx, pal, orig, box, text, bgi, it):
    if it.get('mode') == 'exact': return paint_exact(idx, pal, orig, box, text, bgi, it)
    if it.get('mode') == 'chip': return paint_chip(idx, pal, orig, tuple(box), text, it)
    if it.get('mode') == 'mask': return paint_mask(idx, pal, orig, tuple(box), text, it)
    if it.get('mode') == 'plate': return paint_plate(idx, pal, orig, tuple(box), text, it)
    box = grow_box(orig, pal, shrink_to_text(orig, pal, tuple(box)), bgi)
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    A = analyse(orig, pal, box, bgi)
    if A is None: return
    S = 4
    region = idx[y0:y1, x0:x1]
    if A['kind'] == 'alpha':
        # 상자에 닿은 원래 글자 조각(테두리·그림자)이 상자 밖으로 삐져나온 부분까지 투명으로
        H_, W_ = orig.shape
        xa, ya, xb, yb = max(0, x0 - 4), max(0, y0 - 4), min(W_, x1 + 4), min(H_, y1 + 4)
        om = pal[orig[ya:yb, xa:xb]][..., 3] > 8
        lab, n = ndimage.label(om)
        inb = np.zeros_like(om); inb[y0 - ya:y1 - ya, x0 - xa:x1 - xa] = True
        hit = set(np.unique(lab[inb & om]).tolist()) - {0}
        # 상자 근처(3px)의 반투명 그림자 조각도
        near = np.zeros_like(om); near[max(0, y0 - ya - 3):y1 - ya + 3, max(0, x0 - xa - 3):x1 - xa + 3] = True
        for k in set(np.unique(lab[near & om]).tolist()) - {0}:
            if (pal[orig[ya:yb, xa:xb]][..., 3][lab == k] < 100).mean() > 0.6: hit.add(k)
        ok = []
        for k in hit:
            ys_, xs_ = np.nonzero(lab == k)
            if (inb[ys_, xs_]).mean() >= 0.6: ok.append(k)   # 대부분 상자 안인 덩어리만(이웃 글자 보호)
        kill = np.isin(lab, ok) & ~inb
        cur = idx[ya:yb, xa:xb]
        cur[kill & (cur == orig[ya:yb, xa:xb])] = bgi
    # 1) 바탕
    if A['kind'] == 'alpha':
        base = np.zeros((h, w, 4), np.float32)
    else:
        base = A['bgimg'].copy()
    if it.get('mode') == 'clear' or not text.strip():
        out = base
    else:
        fill = np.array(list(it['fill'])[:3] + [128], np.float32) if 'fill' in it else A['fill'].copy()
        outline = np.array(list(it['outline'])[:3] + [128], np.float32) if 'outline' in it else A['outline'].copy()
        t = int(it.get('t', A['t']))
        fill[3] = outline[3] = 128
        if A['kind'] == 'panel':
            # 판 위 글자 통일 규칙: 원본이 테두리+대비가 충분하면 원본 색(표준화), 아니면 흰 글자 + 짙은 테두리
            good = A['t'] > 0 and abs(lum(A['fill']) - lum(A['outline'])) >= 60 and A.get('rowc') is not None and float(np.std(A['rowc'][:, :3] @ np.array([0.299, 0.587, 0.114]))) < 8
            if False and good and 'fill' not in it and 'outline' not in it:
                fill = standard_fill(A['fill'], A['outline'])
                outline = np.array([255, 255, 255, 128] if lum(A['outline']) > lum(A['fill']) else [20, 20, 30, 128], np.float32)
                t = int(it.get('t', max(1, A['t'])))
            elif 'fill' not in it: fill = np.array([255, 255, 255, 128], np.float32)
            if 'outline' not in it:
                bh, bs, bv = colorsys.rgb_to_hsv(*(np.clip(A['bg'][:3], 0, 255) / 255))
                if bv < 0.25:   # 검은 바탕: 원래 테두리 색상을 살려 중간 밝기로
                    oh, os_, ov = colorsys.rgb_to_hsv(*(np.clip(A['outline'][:3], 0, 255) / 255))
                    outline = np.array(list(np.array(colorsys.hsv_to_rgb(oh, max(os_, 0.8) if os_ > 0.1 else 0, 0.8)) * 255) + [128], np.float32)
                else:
                    outline = np.array(list(np.array(colorsys.hsv_to_rgb(bh, max(bs, 0.55) if bs > 0.08 else 0, 0.32)) * 255) + [128], np.float32)
            t = int(it.get('t', 1 if A['gh'] < 16 else 2))
        else:
            # 투명 바탕 메뉴 글자 통일 규칙
            hue_src = A['fill'] if 'fill' not in it else np.array(list(it['fill'])[:3] + [128], np.float32)
            hh_, ss_, vv_ = colorsys.rgb_to_hsv(*(np.clip(A['fill'][:3], 0, 255) / 255))
            oh_, os2, ov_ = colorsys.rgb_to_hsv(*(np.clip(A['outline'][:3], 0, 255) / 255))
            if ss_ < 0.25 and os2 >= 0.25: hh_, ss_ = oh_, os2          # 흰 글자+유채색 테두리 → 테두리 색이 고유색
            chroma = ss_ >= 0.25
            big = A['gh'] >= 22
            style = it.get('style', 'big' if big else 'small')
            if 'fill' not in it and 'outline' not in it and A['gh'] <= 15:
                fill = A['fill'].copy(); fill[3] = 128; t = 0      # 작은 평문 글자: 원래 모양 그대로
            elif 'fill' not in it and 'outline' not in it:
                if style == 'big':
                    fill = np.array(list(np.array(colorsys.hsv_to_rgb(hh_, 0.85, 0.95)) * 255) + [128], np.float32) if chroma else np.array([250, 250, 250, 128], np.float32)
                    outline = np.array([255, 255, 255, 128], np.float32) if chroma else np.array([30, 40, 110, 128], np.float32)
                    t = int(it.get('t', 2)); A['shadow'] = (30, 40, 110)
                else:
                    fill = np.array([255, 255, 255, 128], np.float32)
                    outline = np.array(list(np.array(colorsys.hsv_to_rgb(hh_, 0.85, 0.72)) * 255) + [128], np.float32) if chroma else np.array([30, 40, 110, 128], np.float32)
                    t = int(it.get('t', 1 if A['gh'] < 16 else 2)); A['outer'] = (255, 255, 255)
            elif t == 0:
                t = 1 if h < 20 else 2
        gh = max(6, A['gh'] - 2 * t)
        if 'gh' in it: gh = max(6, int(it['gh']) - 2 * t) if it['gh'] > 0 else gh
        g = glyph_mask(text, max(1, w - 2 * t), h - 2 * t, gh, it.get('weight', 'heavy'), it.get('align', 'center'))
        gh_, gw_ = g.shape
        M = np.zeros((h * S, w * S), np.float32)
        oy = int(round((A['gy'] + A['gh'] / 2) * S - gh_ / 2)); oy = max(t * S, min(h * S - gh_ - t * S, oy))
        al = it.get('align', 'center')
        ox = t * S if al == 'left' else (w * S - gw_ - t * S if al == 'right' else (w * S - gw_) // 2)
        M[oy:oy + gh_, ox:ox + gw_] = g[:h * S - oy, :w * S - ox]
        core = M > 0.5
        if t:
            comp = ndimage.distance_transform_edt(~core) <= t * S
        else:
            comp = core
        ext = None
        if A.get('outer') is not None or A.get('shadow') is not None:
            if A.get('outer') is not None:
                ext = ndimage.distance_transform_edt(~comp) <= 1 * S; extc = np.array(list(A['outer']) + [128], np.float32)
            else:
                sh = np.zeros_like(comp); d_ = 2 * S
                sh[d_:, d_:] = comp[:-d_, :-d_]; ext = sh | comp; extc = np.array(list(A['shadow']) + [128], np.float32)
            ecov = ext.reshape(h, S, w, S).mean((1, 3))[..., None]
            base = extc * ecov + base * (1 - ecov)
            base[..., 3] = np.maximum(base[..., 3], 128 * ecov[..., 0])
        fcov = core.reshape(h, S, w, S).mean((1, 3))[..., None]
        ccov = comp.reshape(h, S, w, S).mean((1, 3))[..., None]
        col = outline * (1 - fcov) + fill * fcov
        col = col * np.where(ccov > 0, 1, 0)
        if t:
            colr = np.where(ccov > 0, (outline * (ccov - fcov) + fill * fcov) / np.maximum(ccov, 1e-6), 0)
        else:
            colr = fill[None, None, :].repeat(h, 0).repeat(w, 1)
        a = ccov
        out = colr * a + base * (1 - a)
        out[..., 3] = np.maximum(base[..., 3], 128 * a[..., 0])
    q = texedit.quantize(out, pal)
    if A['kind'] == 'panel':
        # 상자 밖 2px 테두리의 원래 글자 흔적도 같은 줄 바탕색으로
        H_, W_ = idx.shape
        for yy in range(max(0, y0 - 3), min(H_, y1 + 3)):
            rc = A['bg']
            xs_ = list(range(max(0, x0 - 3), x0)) + list(range(x1, min(W_, x1 + 3)))
            if yy < y0 or yy >= y1: xs_ = list(range(max(0, x0 - 3), min(W_, x1 + 3)))
            for xx in xs_:
                p = pal[orig[yy, xx]].astype(np.float32)
                near_glyph = min(np.abs(p[:3] - A['fill'][:3]).sum(), np.abs(p[:3] - A['outline'][:3]).sum()) < 90
                far_x = xx - 4 if xx < x0 else xx + 4
                if 0 <= far_x < W_:
                    q2 = pal[orig[yy, far_x]].astype(np.float32)
                    if np.abs(q2[:3] - rc[:3]).sum() > 60 and q2[3] >= 64: continue   # 바깥으로 이어지는 이웃 글자
                if p[3] >= 64 and near_glyph and np.abs(p[:3] - rc[:3]).sum() > 60 and idx[yy, xx] == orig[yy, xx]:
                    idx[yy, xx] = texedit.quantize(rc[None, None, :], pal)[0, 0]
    if A['kind'] == 'alpha':
        q[out[..., 3] < 6] = bgi
    region[:] = q

def snap_box(orig, pal, box, bgi):
    """투명 바탕 글자: 상자 중심 근처 글자 덩어리들(무게중심이 상자 안)의 합집합으로 상자를 맞춤."""
    x0, y0, x1, y1 = box; H, W = orig.shape
    A = (pal[orig][..., 3] > 24) & (orig != bgi)
    xa, ya, xb, yb = max(0, x0 - 8), max(0, y0 - 6), min(W, x1 + 8), min(H, y1 + 6)
    sub = A[ya:yb, xa:xb]
    ring = np.concatenate([A[max(0, y0 - 2):y0, x0:x1].ravel(), A[y1:y1 + 2, x0:x1].ravel()])
    lab, n = ndimage.label(ndimage.binary_dilation(sub, iterations=1))
    xs, ys = [], []
    for k in range(1, n + 1):
        yy, xx = np.nonzero((lab == k) & sub)
        if len(yy) == 0: continue
        cy, cx = yy.mean() + ya, xx.mean() + xa
        inside = ((xx + xa >= x0) & (xx + xa < x1) & (yy + ya >= y0) & (yy + ya < y1)).mean()
        if x0 - 1 <= cx < x1 + 1 and y0 - 1 <= cy < y1 + 1 and inside >= 0.6:
            xs += [xx.min() + xa, xx.max() + xa + 1]; ys += [yy.min() + ya, yy.max() + ya + 1]
    if not xs: return box
    nb = (min(xs), min(ys), max(xs), max(ys))
    ix = max(0, min(nb[2], x1) - max(nb[0], x0)) * max(0, min(nb[3], y1) - max(nb[1], y0))
    ua = (nb[2] - nb[0]) * (nb[3] - nb[1]) + (x1 - x0) * (y1 - y0) - ix
    if ua <= 0 or ix / ua < 0.6: return box
    return nb

def paint_all(idx, pal, orig, items, bgi):
    """같은 텍스처 안에서 원래 상자 높이가 같은 항목끼리 글자 높이·색을 통일."""
    import collections
    info = []
    tr = (pal[orig][..., 3] < 8).mean() > 0.3
    items2 = []
    for it in items:
        if it.get('ko') is None: continue
        if tr and it.get('mode') is None and 'nosnap' not in it and it['box'][3] - it['box'][1] < 22:
            it = dict(it, box=list(snap_box(orig, pal, tuple(it['box']), bgi)))
        items2.append(it)
    for it in items2:
        if it.get('mode') in ('plate', 'mask', 'chip', 'exact'): info.append((it, None)); continue
        b = shrink_to_text(orig, pal, tuple(it['box']))
        A = analyse(orig, pal, b, bgi)
        info.append((it, A))
    grp = collections.defaultdict(list)
    for it, A in info:
        if A is None: continue
        h = it['box'][3] - it['box'][1]
        grp[(h // 3, A['kind'])].append(A)
    for it, A in info:
        if A is None:
            if it.get('mode') in ('plate', 'mask', 'chip', 'exact'): paint(idx, pal, orig, it['box'], it['ko'], bgi, it)
            continue
        h = it['box'][3] - it['box'][1]
        G = grp[(h // 3, A['kind'])]
        it2 = dict(it)
        if len(G) >= 3 and 'gh' not in it:
            it2['gh'] = int(np.median([g['gh'] for g in G])) - 2 * int(it.get('t', 0))
        if False:
            F = np.array([g['fill'][:3] for g in G]); O = np.array([g['outline'][:3] for g in G])
            # 색상이 비슷한 항목끼리만(개별 색 구분이 의도된 목록은 유지)
            sat = (F.max(1) - F.min(1)) / np.maximum(F.max(1), 1)
            top = sat >= np.median(sat)
            fm = np.median(F[top], 0); om = np.median(O[top], 0)
            h0 = colorsys.rgb_to_hsv(*(A['fill'][:3] / 255))[0]; h1 = colorsys.rgb_to_hsv(*(fm / 255))[0]
            if min(abs(h0 - h1), 1 - abs(h0 - h1)) < 0.12 or sat.max() < 0.25:
                it2['fill'] = [float(x) for x in fm]
                it2['outline'] = [float(x) for x in om]
        paint(idx, pal, orig, it['box'], it['ko'], bgi, it2)
