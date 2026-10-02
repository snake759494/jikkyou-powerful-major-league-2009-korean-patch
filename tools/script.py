"""바이트코드 대사 스크립트(P3615 등): 명령(F2xx/F3xx/FExx/FFFD+인자 등) 사이의 대사 조각을 같은 길이로 제자리 번역.
대사 안 태그: {FC0x}(줄바꿈/대기/색), {F0xx}{F1xx}(변수·표정), {FFE8:xxxx}(이름 변수, 인자 포함 2코드)."""
import sys, os, struct, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charmap import CODE2CH
import kotext
KANA = lambda c: 0x11a <= c < 0x1cf or 0x2c2 <= c < 0xe9c

def tokens(a, s=0):
    """(시작, 코드수, 종류, 표시) 목록. 종류 t=글자, g=대사 안 태그, x=명령."""
    i = s; n = len(a); out = []
    while i < n:
        c = a[i]
        if c == 0xFFE8 and i + 1 < n: out.append((i, 2, 'g', '{FFE8:%04X}' % a[i + 1])); i += 2; continue
        if c == 0xFFFD and i + 1 < n: out.append((i, 2, 'x', None)); i += 2; continue
        if c < 0xF000 and c in CODE2CH: out.append((i, 1, 't', CODE2CH[c])); i += 1; continue
        if 0xFC00 <= c <= 0xFCFF or 0xF000 <= c <= 0xF1FF: out.append((i, 1, 'g', '{%04X}' % c)); i += 1; continue
        out.append((i, 1, 'x', None)); i += 1
    return out

def units(b):
    a = struct.unpack('<%dH' % (len(b) // 2), b[:len(b) // 2 * 2])
    T = tokens(a)
    res = []; cur = []
    def flush():
        if not cur: return
        # 앞뒤 태그 제거(대사 바깥 제어)
        while cur and cur[0][2] == 'g': cur.pop(0)
        while cur and cur[-1][2] == 'g' and not cur[-1][3].startswith('{FC'): cur.pop()
        txt = [t for t in cur if t[2] == 't']
        if sum(1 for t in txt if KANA(a[t[0]])) >= 2:
            s = cur[0][0]; e = cur[-1][0] + cur[-1][1]
            res.append(dict(off=s * 2, n=e - s, jp=''.join(t[3] for t in cur).replace('{FC00}', '\n')))
    for t in T:
        if t[2] == 'x':
            flush(); cur = []
        else:
            cur.append(t)
    flush()
    return res

TAG = re.compile(r'\{FFE8:[0-9A-F]{4}\}|\{[0-9A-F]{4}\}')
def encode(ko):
    out = []
    for m in re.finditer(r'\{FFE8:([0-9A-F]{4})\}|\{([0-9A-F]{4})\}|\n|.', ko, re.S):
        g = m.group(0)
        if m.group(1): out += [0xFFE8, int(m.group(1), 16)]
        elif m.group(2): out.append(int(m.group(2), 16))
        elif g == '\n': out.append(0xFC00)
        else: out += kotext.codes(g)
    return out

def patch(b, units_ko):
    """units_ko: [(off, n, ko)] → 같은 길이로 덮어쓰기(짧으면 마지막 태그 앞에 공백)."""
    b = bytearray(b); probs = []
    for off, n, ko in units_ko:
        cs = encode(ko)
        if len(cs) > n: probs.append((off, len(cs), n, ko)); continue
        pad = n - len(cs)
        # 끝의 FCxx 태그 앞에 공백 채움
        k = len(cs)
        while k > 0 and 0xFC00 <= cs[k - 1] <= 0xFCFF: k -= 1
        cs = cs[:k] + [0] * pad + cs[k:]
        b[off:off + 2 * n] = struct.pack('<%dH' % n, *cs)
    return bytes(b), probs

if __name__ == '__main__':
    b = open(sys.argv[1], 'rb').read()
    U = units(b)
    print(len(U), sum(u['n'] for u in U))
    for u in U[:15]: print(hex(u['off']), u['n'], repr(u['jp'][:80]))
