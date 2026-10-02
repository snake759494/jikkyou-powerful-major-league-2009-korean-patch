"""번역 단위 추출 → translation/units.jsonl
단위: {id, src('ELF'|'P0123'), off(바이트), cap(u16 칸수), kind, jp}
 - text: 0xFFFF 로 끝나는 문자열(앞쪽 0 제외). cap = 끝(FFFF)까지 칸수.
 - name9/name12: 선수 DB 고정 필드(0 채움).
문자열 표기: 줄바꿈 \n, 비문자 코드 {XXXX}."""
import sys, os, json, struct, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fastscan, textscan, proj, names
from charmap import CODE2CH
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
NAME_DBS = [4095, 4087, 3704, 3614, 3613]

def clean(a):
    """문자열로 볼 만한가: 코드 대부분이 글자이고 가나/한자 포함."""
    if len(a) == 0: return False
    known = np.array([(c in CODE2CH) or c == 0x1ffe or (0x1f00 <= c < 0x2000) or (0xd000 <= c < 0xd100) for c in a])
    kana = ((a >= 0x11a) & (a < 0x1cf)) | (a == 0x1b)
    kanji = (a >= 0x2c2) & (a < 0xe9c)
    alnum = (a >= 0xcf) & (a < 0x11a)
    if known.mean() < 0.97: return False
    if kana.sum() + kanji.sum() == 0:
        return False
    if len(a) >= 4 and (kana.sum() + kanji.sum() + alnum.sum()) < 0.5 * len(a): return False
    # 같은 글자 반복(이미지 데이터) 배제
    if len(a) >= 4 and len(set(a.tolist())) <= 2: return False
    if len(a) == 1 and not kanji.any(): return False
    return True

def strings(b, lo=0x20):
    out = []
    for o, n in fastscan.scan(b, lo, align=0):
        a = np.frombuffer(b[o:o + 2 * n], '<u2')
        nz = np.nonzero(a)[0]
        if len(nz) == 0: continue
        s = int(nz[0]); a2 = a[s:]
        if clean(a2): out.append((o + 2 * s, len(a2)))
    return out

def main():
    d, ents = proj.load(); E = {e['idx']: e for e in ents}
    units = []
    def add(src, off, cap, kind, b, n):
        a = struct.unpack_from('<%dH' % n, b, off)
        nl = 0xd000 if 0xd000 in a else 0x1ffe
        if 0xd000 in a and 0x1ffe in a: nl = 0   # 섞임: 태그로
        jp = textscan.dec(b, off, n)
        if nl == 0: jp = ''.join('{D000}' if c == 0xd000 else ch for c, ch in zip(a, jp)) if len(jp) == n else jp
        units.append(dict(id=len(units), src=src, off=off, cap=cap, kind=kind, nl=nl, jp=jp))
    elf = open(os.path.join(ROOT, 'work', 'SLPM_551.55'), 'rb').read()
    for o, n in strings(elf, 0x600000): add('ELF', o, n, 'text', elf, n)
    for e in ents:
        b = open(os.path.join(ROOT, 'work', 'pack', e['name']), 'rb').read()
        src = 'P%04d' % e['idx']
        if e['idx'] in NAME_DBS:
            for o, t1, t2, t3 in names.find_triples(b):
                if sum(1 for ch in t2 if 'ァ' <= ch <= 'ヶ') < 2: continue
                for off, cap, t in ((o, 9, t1), (o + 0x12, 12, t2), (o + 0x2a, 12, t3)):
                    if t: units.append(dict(id=len(units), src=src, off=off, cap=cap, kind='name%d' % cap, jp=t))
            continue
        for o, n in strings(b): add(src, o, n, 'text', b, n)
    with open(os.path.join(ROOT, 'translation', 'units.jsonl'), 'w', encoding='utf-8') as f:
        for u in units: f.write(json.dumps(u, ensure_ascii=False) + '\n')
    return units

if __name__ == '__main__':
    import collections
    U = main()
    c = collections.Counter(u['src'] for u in U)
    ch = collections.Counter()
    for u in U: ch[u['src']] += len(u['jp'])
    print(len(U), sum(len(u['jp']) for u in U))
    for k, v in ch.most_common(40): print(k, c[k], v)
    print('srcs', len(c))
