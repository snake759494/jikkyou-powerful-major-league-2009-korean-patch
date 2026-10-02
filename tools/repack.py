"""포인터 참조 문자열 재배치.
문자열 = [속성 u16][글자...][FFFF], 포인터(0x80000000|오프셋)는 속성 위치를 가리킴(4바이트 정렬)."""
import sys, os, struct, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ptrs

def analyze(b, units):
    """units: 이 파일의 번역 단위(off=첫 글자). 반환: 문자열 목록 [(attr_off, unit or None, end_off)] 과 커버리지."""
    P = ptrs.pointers(b)
    T = collections.defaultdict(list)
    for p, t in P: T[t].append(p)
    res = []
    for u in units:
        o = u['off']
        # 앞쪽 0 들을 거슬러 포인터 대상 찾기
        tgt = o if o in T else None
        a = o - 2
        while tgt is None and a >= o - 16 and struct.unpack_from('<H', b, a)[0] == 0:
            if a in T: tgt = a
            a -= 2
        end = o
        while struct.unpack_from('<H', b, end)[0] != 0xffff: end += 2
        res.append((tgt, u, end + 2))
    return res, T

if __name__ == '__main__':
    import proj
    d, ents = proj.load(); E = {e['idx']: e for e in ents}
    S = [json.loads(l) for l in open('translation/units_sel.jsonl', encoding='utf-8')]
    by = collections.defaultdict(list)
    for u in S: by[u['src']].append(u)
    for src in sys.argv[1:]:
        b = open('work/pack/' + E[int(src[1:])]['name'], 'rb').read()
        res, T = analyze(b, sorted(by[src], key=lambda u: u['off']))
        pointed = sum(1 for t, u, e in res if t is not None)
        # 미참조 문자열 앞 바이트
        print(src, len(res), 'pointed', pointed)
        for t, u, e in res:
            if t is None: print('   miss', hex(u['off']), u['jp'][:20], b[u['off'] - 8:u['off']].hex(' ')); break
