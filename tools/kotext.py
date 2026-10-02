"""한국어 문자열 → 게임 u16 코드."""
import os, sys, struct, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charmap import CH2CODE, CODE2CH
from build_font import HANGUL, HSTART
HIDX = {h: HSTART + i for i, h in enumerate(HANGUL)}
FULL = {chr(c): chr(c + 0xFEE0) for c in range(0x21, 0x7F)}
FULL[' '] = '　'
FULL['~'] = '〜'
ALIAS = {'·': '・', '"': '”', "'": '’', '-': '−', '－': '−', '—': '―', '–': '−', '~': '〜', '～': '〜'}

def codes(s):
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        m = re.match(r'\{([0-9A-Fa-f]{4})\}', s[i:])
        if m: out.append(int(m.group(1), 16)); i += 6; continue
        if ch == '\n': out.append(0x1FFE)
        elif ch in HIDX: out.append(HIDX[ch])
        elif ch in CH2CODE: out.append(CH2CODE[ch])
        elif ch in ALIAS and ALIAS[ch] in CH2CODE: out.append(CH2CODE[ALIAS[ch]])
        elif ch in FULL and FULL[ch] in CH2CODE: out.append(CH2CODE[FULL[ch]])
        else: raise ValueError('인코딩 불가 문자: %r in %r' % (ch, s))
        i += 1
    return out

def enc(s): return struct.pack('<%dH' % len(codes(s)), *codes(s))
