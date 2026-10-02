"""u16 문자열 스캔: 유효 코드(<0xF40, 제어 0x1Fxx/0x2xxx 일부) 연속 + 0xFFFF 끝."""
import struct, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charmap import CODE2CH

def ok(c):
    return c in CODE2CH or c == 0x1ffe or (0x1f00 <= c < 0x2000)

def scan(b, start=0, end=None, minlen=2):
    end = end or len(b)
    res = []
    i = start & ~1
    while i < end - 2:
        j = i; n = 0; kana = 0
        while j < end - 1:
            c = b[j] | (b[j + 1] << 8)
            if c == 0xffff: break
            if not ok(c): break
            if 0x11a <= c < 0xe9c or 0xbc <= c < 0x11a: kana += 1
            n += 1; j += 2
        if j < end - 1 and b[j] == 0xff and b[j + 1] == 0xff and n >= minlen and kana >= 1:
            res.append((i, n)); i = j + 2
        else:
            i += 2
    return res

def dec(b, off, n):
    out = []
    for k in range(n):
        c = b[off + 2 * k] | (b[off + 2 * k + 1] << 8)
        if c == 0x1ffe: out.append('\n')
        elif c in CODE2CH: out.append(CODE2CH[c])
        else: out.append('{%04X}' % c)
    return ''.join(out)
