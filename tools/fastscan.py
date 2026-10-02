"""빠른 u16 문자열 스캔: 0xFFFF 로 끝나는, 앞쪽으로 유효 코드가 이어진 구간."""
import numpy as np
def scan(b, lo=0, hi=None, align=0):
    hi = hi or len(b)
    out = []
    for ph in ((0, 1) if align is None else (align,)):
        a = np.frombuffer(b[lo + ph: hi - ((hi - lo - ph) % 2)], '<u2')
        valid = (a < 0xF40) | ((a >= 0x1F00) & (a < 0x2000)) | ((a >= 0xD000) & (a < 0xD100))
        ends = np.nonzero(a == 0xFFFF)[0]
        inv = np.nonzero(~valid)[0]
        for e in ends:
            k = np.searchsorted(inv, e) - 1
            s = inv[k] + 1 if k >= 0 else 0
            if e - s >= 1: out.append((lo + ph + 2 * int(s), int(e - s)))
    return out
def textish(b, o, n):
    a = np.frombuffer(b[o:o + 2 * n], '<u2')
    nz = np.nonzero(a)[0]
    if len(nz) == 0: return False
    a = a[nz[0]:]
    kana = ((a >= 0x11a) & (a < 0x1cf)) | (a == 0x1b)
    kanji = (a >= 0x2c2) & (a < 0xe9c)
    good = kana | kanji | (a == 0x1ffe) | ((a >= 1) & (a < 0x5e)) | ((a >= 0xcf) & (a < 0x11a))
    # 가나 연속 2개 이상
    run = (kana[:-1] & kana[1:]).sum() if len(a) > 1 else 0
    return len(a) >= 2 and good.mean() >= 0.85 and (kana.sum() + kanji.sum()) >= max(2, 0.4 * len(a)) and (run >= 1 or kanji.sum() >= 2)
