"""TEX 텍스처: 'TEX\0' 헤더 0x40, +0x10 w,h(u16), +0x17 psm(0x13=8bpp, 0x14=4bpp). 픽셀 뒤 팔레트(RGBA, 8bpp는 CSM1 스위즐)."""
import struct, numpy as np, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import swz
from PIL import Image
def csm1(pal):
    p = pal.copy()
    for i in range(0, 256, 32):
        p[i + 8:i + 16], p[i + 16:i + 24] = pal[i + 16:i + 24].copy(), pal[i + 8:i + 16].copy()
    return p
def parse(b, o):
    w, h = struct.unpack_from('<HH', b, o + 0x10)
    psm = b[o + 0x17] & 0x7f
    return w, h, psm
def pal_off(b, o):
    """텍스처 뒤 첫 'PAL\0' 청크의 데이터 위치."""
    w, h, psm = parse(b, o)
    end = o + 0x40 + (w * h if psm == 0x13 else w * h // 2)
    p = b.find(b'PAL', end)
    if p >= 0 and p - end < 0x1000 and p + 0x40 + (1024 if psm == 0x13 else 64) <= len(b): return p + 0x40
    # 여러 텍스처가 팩 끝의 팔레트 하나를 공유하는 경우
    q = b.find(b'PAL\x00', end)
    need = 1024 if psm == 0x13 else 64
    return q + 0x40 if q >= 0 and q + 0x40 + need <= len(b) else end

def decode(b, o, swz_pal=True, swz_px=None):
    w, h, psm = parse(b, o)
    if swz_px is None: swz_px = bool(b[o + 0x17] & 0x80)
    d = o + 0x40
    if psm == 0x13:
        px = swz.unswizzle8(b[d:d + w * h], w, h) if swz_px else np.frombuffer(b[d:d + w * h], np.uint8).reshape(h, w)
        po = pal_off(b, o); pal = np.frombuffer(b[po:po + 1024], np.uint8).reshape(256, 4).copy()
        if swz_pal: pal = csm1(pal)
    elif psm == 0x14:
        raw = np.frombuffer(b[d:d + w * h // 2], np.uint8)
        px = swz.unswizzle4(b[d:d + w * h // 2], w, h) if swz_px else np.stack([raw & 15, raw >> 4], 1).reshape(h, w)
        po = pal_off(b, o); pal = np.frombuffer(b[po:po + 64], np.uint8).reshape(16, 4).copy()
    else:
        return None
    rgba = pal[px].copy()
    rgba[..., 3] = np.minimum(255, rgba[..., 3].astype(int) * 2)
    return Image.fromarray(rgba, 'RGBA')
