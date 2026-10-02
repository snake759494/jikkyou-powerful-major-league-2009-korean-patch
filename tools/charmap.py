"""게임 문자코드 ↔ 유니코드. 0~0x2C1: JIS 1~8행(94자씩), 0x2C2~: JIS 1수준 한자 연속, 그 뒤 추가 글자(extra.json)."""
import json, os
KSTART = 0x2C2
HERE = os.path.dirname(os.path.abspath(__file__))

def jis(row, cell):
    try: return bytes([0xA0 + row, 0xA0 + cell]).decode('euc_jp')
    except Exception: return None

def build():
    m = {}
    for c in range(KSTART):
        ch = jis(c // 94 + 1, c % 94 + 1)
        if ch: m[c] = ch
    i = 0
    for row in range(16, 48):
        for cell in range(1, 95):
            ch = jis(row, cell)
            if ch is None: continue
            m[KSTART + i] = ch; i += 1
    p = os.path.join(HERE, '..', 'translation', 'extra_chars.json')
    if os.path.exists(p):
        for k, v in json.load(open(p, encoding='utf-8')).items(): m[int(k, 16)] = v
    return m

CODE2CH = build()
CH2CODE = {}
for k, v in CODE2CH.items(): CH2CODE.setdefault(v, k)
