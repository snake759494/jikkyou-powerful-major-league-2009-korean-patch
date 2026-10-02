"""파워프로 폰트(ScsComMainMonPM4.pack) 형식.
파일(PACK 헤더 뒤): [u8 ?][u8 ?][u16 글자수][u32 오프셋 × 글자수][글리프 데이터...]
글리프: [n][비트열 n바이트, MSB 먼저][리터럴 바이트들]. 출력 28행 × 11바이트(22px, 4bpp 하위니블=왼쪽 픽셀).
각 바이트열(열) j 마다 세로 반복 카운터. 카운터>0 이면 저장값 출력.
아니면 비트 0 → 리터럴 1바이트; 비트 1 → 가로폭 w(2비트, 0이면 4+4비트), 세로 h(동일), 값 1바이트 → w열 × h행 채움."""
import struct
import numpy as np
W, H = 11, 28

class Bits:
    def __init__(s, b): s.b = b; s.i = 0
    def bit(s):
        v = (s.b[s.i >> 3] >> (7 - (s.i & 7))) & 1; s.i += 1; return v
    def n(s, k):
        v = 0
        for _ in range(k): v = v * 2 + s.bit()
        return v

def decode(g):
    n = g[0]; bits = Bits(g[1:1 + n]); lit = 1 + n
    cnt = [0] * W; val = [0] * W
    out = np.zeros((H, W), np.uint8)
    for y in range(H):
        for j in range(W):
            if cnt[j]:
                cnt[j] -= 1; out[y, j] = val[j]; continue
            if bits.bit() == 0:
                out[y, j] = g[lit]; lit += 1; continue
            w = bits.n(2)
            if w == 0: w = 4 + bits.n(4)
            h = bits.n(2)
            if h == 0: h = 4 + bits.n(4)
            v = g[lit]; lit += 1
            for k in range(w):
                if j + k < W: val[j + k] = v; cnt[j + k] = h
            cnt[j] -= 1; out[y, j] = val[j]
    return out, lit

def to_pixels(b):
    p = np.zeros((H, W * 2), np.uint8); p[:, 0::2] = b & 15; p[:, 1::2] = b >> 4; return p

def load(path):
    d = open(path, 'rb').read()[0x20:]
    return d

def fonts(d):
    """(시작, 글자수, 오프셋목록, 데이터시작) 두 폰트."""
    res = []
    o = 0
    while o + 4 <= len(d):
        cnt = struct.unpack_from('<H', d, o + 2)[0]
        if cnt == 0: break
        offs = struct.unpack_from('<%dI' % cnt, d, o + 4)
        base = o + 4 + 4 * cnt
        res.append((o, cnt, offs, base))
        end = base + offs[-1]
        _, used = decode(d[end:end + 400])
        o = (end + used + 0x1ff) & ~0x1ff
        if len(res) >= 2: break
    return res

class BitW:
    def __init__(s): s.bits = []
    def put(s, v, k):
        for i in range(k - 1, -1, -1): s.bits.append((v >> i) & 1)
    def bytes(s):
        b = s.bits + [0] * (-len(s.bits) % 8)
        return bytes(int(''.join(map(str, b[i:i + 8])), 2) for i in range(0, len(b), 8))

def _len(bw, n):
    if 1 <= n <= 3: bw.put(n, 2)
    else: bw.put(0, 2); bw.put(n - 4, 4)

def encode(b):
    """b: (28,11) 바이트 배열 → 글리프 바이트열 (탐욕 블록 압축, decode 와 왕복 일치)."""
    b = np.asarray(b, np.uint8)
    cover = np.zeros((H, W), bool)        # 이미 블록으로 덮인 칸
    cnt = [0] * W
    bw = BitW(); lit = bytearray()
    for y in range(H):
        for j in range(W):
            if cnt[j]:
                cnt[j] -= 1; continue
            v = b[y, j]
            best = (1, 1)
            # 가로 최대: 같은 행, 카운터 0, 값 v
            wmax = 0
            while j + wmax < W and wmax < 19 and cnt[j + wmax] == 0 and b[y, j + wmax] == v: wmax += 1
            for w in range(1, wmax + 1):
                h = 1
                while y + h < H and h < 19 and (b[y + h, j:j + w] == v).all(): h += 1
                if w * h > best[0] * best[1]: best = (w, h)
            w, h = best
            if w * h <= 1:
                bw.put(0, 1); lit.append(v)
            else:
                bw.put(1, 1); _len(bw, w); _len(bw, h); lit.append(v)
                for k in range(w): cnt[j + k] = h
                cnt[j] -= 1
    bits = bw.bytes()
    assert len(bits) < 256
    return bytes([len(bits)]) + bits + bytes(lit)

def from_pixels(p):
    p = np.asarray(p, np.uint8)
    return (p[:, 0::2] & 15) | ((p[:, 1::2] & 15) << 4)
