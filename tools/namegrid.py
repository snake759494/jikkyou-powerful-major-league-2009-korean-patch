"""이름 입력판 한글화.
 - 한자 탭(읽기별 목록 44칸): 첫 글자(가나 키)는 그대로 두고 글리프만 라벨 음절로 바꾸며, 나머지를 초성 순 한글 음절로 채움.
 - 히라가나 탭(75칸): 이름에 자주 쓰는 음절."""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kotext
from charmap import CH2CODE
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
HIRA_TABLE = 0x6bf6f0
KANA_TAB = 0x6c6500      # 히라가나 탭 격자: 10행 × (12칸 + FFFF + 여백3)
COMMON = ('김이박최정강조윤장임한오서신권황안송전홍유고문양손배백허남심노하곽성차주우구민류진나지엄원천방공현채'
          '준영수희재호은혜경미선태석동규상승철훈빈연아도형기라리리')
COMMON120 = ('김이박최정강조윤장임한오서신권황안송전홍유고문양손배백허남심노하곽성차주우구민류진나지엄원천방공현채변염여추도소석선설마길'
             '연위표명기반왕금옥육인맹제모탁국어은편용예경봉사부가복태목형피두감음빈동온호범좌갈상승수영희재혜미철훈규빛아리라린솔별')
def common120():
    s = []
    for ch in COMMON120:
        if ch not in s: s.append(ch)
    from build_font import HANGUL
    for ch in HANGUL:
        if len(s) >= 120: break
        if ch not in s: s.append(ch)
    return s[:120]

def common75():
    s = []
    for ch in COMMON:
        if ch not in s: s.append(ch)
    extra = '다마바사자카타파하가너더러머버서어저처커터퍼허'
    for ch in extra:
        if len(s) >= 75: break
        if ch not in s: s.append(ch)
    return s[:75]
def plan():
    return json.load(open(os.path.join(ROOT, 'work', 'kanji_plan.json'), encoding='utf-8'))
def glyph_overrides():
    """가나 키 코드 → 표시할 라벨 글자."""
    P = plan(); ov = {}
    for p in P['plan']: ov[CH2CODE[p['key']]] = p['label']
    for u in P['unused']: ov[CH2CODE[u['key']]] = ' '
    return ov
def patch_elf(e):
    e = bytearray(e)
    P = plan()
    for p in P['plan']:
        cs = [CH2CODE[p['key']]] + kotext.codes(''.join(p['syl'][1:]))
        assert len(cs) <= p['cap']
        o = p['off']
        e[o:o + 2 * p['cap'] + 2] = struct.pack('<%dH' % len(cs), *cs) + b'\xff\xff' + bytes(2 * (p['cap'] - len(cs)))
    for u in P['unused']:
        o = u['off']
        cs = [CH2CODE[u['key']]]
        e[o:o + 2 * u['cap'] + 2] = struct.pack('<H', cs[0]) + b'\xff\xff' + bytes(2 * (u['cap'] - 1))
    # 히라가나 탭 격자(자주 쓰는 음절 120)
    cc = kotext.codes(''.join(common120()))
    for r in range(10):
        o = KANA_TAB + r * 32
        e[o:o + 24] = struct.pack('<12H', *cc[r * 12:(r + 1) * 12])
    # 다른 곳의 히라가나 표(75)
    cs = kotext.codes(''.join(common75()))
    e[HIRA_TABLE:HIRA_TABLE + 150] = struct.pack('<75H', *cs)
    return bytes(e)
