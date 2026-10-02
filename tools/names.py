"""선수 이름 3필드(표시명 9 / 성 12 / 이름 12, u16) 패턴 찾기."""
import sys, os, struct, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charmap import CODE2CH
KATA = set(range(0x178, 0x1cf)) | {0x1b, 0x04, 0x05}   # 가타카나, ー, ．, ・
FULLAL = set(range(0xdf, 0x11a))
def field(b, o, n):
    a = struct.unpack_from('<%dH' % n, b, o)
    s = []
    for i, c in enumerate(a):
        if c == 0:
            if any(a[i:]): return None   # 중간 0 금지
            break
        s.append(c)
    return s
def txt(cs): return ''.join(CODE2CH.get(c, '?') for c in cs)
def find_triples(b):
    a = np.frombuffer(b[:len(b) // 2 * 2], '<u2')
    iskat = np.isin(a, list(KATA | FULLAL))
    res = []
    cand = np.nonzero(iskat[:-1] & iskat[1:])[0]
    seen = set()
    for i in cand:
        o = int(i) * 2
        if o in seen or o + 0x42 > len(b): continue
        if o >= 2 and a[i - 1] in KATA: continue
        f1 = field(b, o, 9); f2 = field(b, o + 0x12, 12); f3 = field(b, o + 0x2a, 12)
        if not f1 or not f2 or f3 is None: continue
        if not all(c in KATA or c in FULLAL for c in f1 + f2 + f3): continue
        t1, t2 = txt(f1), txt(f2)
        if t1.endswith(t2) or t1 == t2[:9]:
            res.append((o, t1, t2, txt(f3))); seen.add(o)
    return res
