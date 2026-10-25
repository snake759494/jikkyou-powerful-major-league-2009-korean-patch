"""경기 HUD 구종명(ELF 0x6b32e9~, 9바이트 칸, 0 끝) → 한국어.
문자열 바이트는 SJIS 가타카나 순번(ァ=1), 게임이 이를 HUD 글꼴(243d955fce97) 칸으로 바꿔 그린다.
가타카나 칸에 한글 음절을 새로 그리고, 구종명을 그 칸의 바이트로 다시 쓴다.
영문 접두(H/V/SFF: 바이트 100/114/111/98)는 그대로 둔다."""
import struct
# 쓸 수 있는 가타카나: 바이트 → 글꼴 칸
_K = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロ'
_SJ = 'ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポマミムメモャヤュユョヨラリルレロ'
_DK = 'ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ'
SLOTS = [b for b in (_SJ.index(c) + 1 for c in _K)] + [_SJ.index(c) + 1 for c in _DK]
CELL = {_SJ.index(c) + 1: 13 + _K.index(c) for c in _K}
CELL.update({_SJ.index(c) + 1: 59 + _DK.index(c) for c in _DK})
H, V, S, F = 100, 114, 111, 98
NAMES = [  # (ELF 파일 오프셋, 칸 길이, 이름)
    (0x6b32e9, 8, '스트레이트'), (0x6b32f2, 8, '투심'), (0x6b32fb, 8, '슬라이더'), (0x6b3304, 8, [H, '슬라이더']),
    (0x6b330d, 8, '컷볼'), (0x6b3316, 8, '커브'), (0x6b331f, 8, '슬로커브'), (0x6b3328, 8, '드롭'),
    (0x6b3331, 8, '드롭커브'), (0x6b333a, 8, '슬러브'), (0x6b3343, 8, '너클커브'), (0x6b334c, 8, '포크'),
    (0x6b3355, 8, '팜볼'), (0x6b335e, 8, '체인지업'), (0x6b3367, 8, '서클체인지'), (0x6b3370, 8, [V, '슬라이더']),
    (0x6b3379, 8, '너클'), (0x6b338b, 8, '포시'), (0x6b3394, 8, '싱커'), (0x6b339d, 8, [H, '싱커']),
    (0x6b33a6, 8, '스크루'), (0x6b33af, 8, '슈트'), (0x6b33b8, 8, [H, '슈트']),
    (0x6b33c1, 9, '싱킹패스트'), (0x6b33ca, 8, '오리지널'), (0x6b33d3, 8, '포심'),
    (0x6b33dc, 8, '요네볼'), (0x6b33e5, 8, '요시볼'), (0x6b33ee, 8, '에모볼'), (0x6b33f7, 8, '면도날슈트'),
    (0x6b3400, 9, '라이징캐논'), (0x6b3409, 9, '소닉라이징'), (0x6b3412, 9, '라이징샷'), (0x6b341b, 8, '스타셰이커'),
]

def glyphs():
    """음절 → 바이트 (등장 순서대로 칸 배정)"""
    m = {}
    for _, _, nm in NAMES:
        for part in (nm if isinstance(nm, list) else [nm]):
            if isinstance(part, str):
                for ch in part:
                    if ch not in m: m[ch] = SLOTS[len(m)]
    return m

def cells():
    """글꼴 칸 → 음절 (hudfont 용)"""
    return {CELL[b]: ch for ch, b in glyphs().items()}

def elf(b):
    m = glyphs()
    for off, n, nm in NAMES:
        bs = []
        for part in (nm if isinstance(nm, list) else [nm]):
            bs += [m[c] for c in part] if isinstance(part, str) else [part]
        assert len(bs) <= n, nm
        b[off:off + n + (n == 8)] = bytes(bs) + bytes(n + (n == 8) - len(bs))
    return b
