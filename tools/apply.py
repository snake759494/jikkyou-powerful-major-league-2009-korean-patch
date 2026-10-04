"""번역 적용: 원본 ELF·팩 → 패치된 바이트.
 - 이름 DB 필드(name9/name12): translation/names/out_p*.jsonl
 - 실황 호출명(P4525): out_v*.jsonl
 - 일반 문장: translation/out/*.jsonl (jp → ko). 가타카나 선수명 문자열은 선수 사전으로 자동 대체.
 - REPACK 소스: 문자열을 빈 슬롯에 순서대로 다시 채우고 0x8000xxxx 포인터 갱신. 그 외: 제자리(칸 수 이내).
"""
import sys, os, json, re, struct, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proj, kotext, ptrs
from make_jobs import REPACK, NAME_DBS
SCRIPTS = {'P3615'}
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
TAG = re.compile(r'\{[0-9A-F]{4}\}')

def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]

def load_translations():
    tr = {}
    ids = json.load(open(os.path.join(ROOT, 'translation', 'text_ids.json'), encoding='utf-8'))
    inv = {v: k for k, v in ids.items()}
    for p in glob.glob(os.path.join(ROOT, 'translation', 'out', '*.jsonl')):
        for o in load_jsonl(p):
            if o.get('id', -1) in inv: tr[inv[o['id']]] = o['ko']
    # 카드 소개문 재작업본 우선
    for p in glob.glob(os.path.join(ROOT, 'translation', 'out_card', '*.jsonl')):
        for o in load_jsonl(p):
            if o.get('id', -1) in inv: tr[inv[o['id']]] = o['ko']
    return tr

def load_names():
    P = {}
    for k in range(8):
        src = {x['id']: x for x in load_jsonl(os.path.join(ROOT, 'translation', 'names', 'p%d.jsonl' % k))}
        p = os.path.join(ROOT, 'translation', 'names', 'out_p%d.jsonl' % k)
        if not os.path.exists(p): continue
        for o in load_jsonl(p):
            s = src[o['id']]
            P[(s['disp'], s['fam'], s['giv'])] = (o['disp'], o['fam'], o['giv'])
    V = {}
    for k in range(4):
        src = {x['id']: x for x in load_jsonl(os.path.join(ROOT, 'translation', 'names', 'v%d.jsonl' % k))}
        p = os.path.join(ROOT, 'translation', 'names', 'out_v%d.jsonl' % k)
        if not os.path.exists(p): continue
        for o in load_jsonl(p): V[src[o['id']]['jp']] = o['ko']
    return P, V

def name_dict(P):
    """가타카나 표시명/성 → 한국어 (가장 많이 쓰인 표기)."""
    c = collections.defaultdict(collections.Counter)
    for (d, f, g), (kd, kf, kg) in P.items():
        if d: c[d][kd] += 1
        if f: c[f][kf] += 1
        if g: c[g][kg] += 1
    return {k: v.most_common(1)[0][0] for k, v in c.items()}

def enc(ko, nl):
    cs = kotext.codes(ko)
    if nl == 0xd000: cs = [0xd000 if c == 0x1ffe else c for c in cs]
    return cs

HL = ['선제', '결승', '역전', '끝내기', '안타', '타', '적시타', '홈런', '동점', '수비', '희생', '플라이',
      '선두타자', '투런', '스리런', '만루', '2루', '3루', '삼진']
def highlight(b):
    """경기 하이라이트 자막 낱말표(ELF 0x64c910: 포인터+길이 19개) — 한국어를 새 풀에 넣고 포인터·길이 갱신."""
    T, POOL, POOL_END, D = 0x64c910, 0x64c880, 0x64c910, 0xFFE80
    pos = POOL
    b[POOL:POOL_END] = bytes(POOL_END - POOL)
    for k, ko in enumerate(HL):
        cs = kotext.codes(ko)
        assert pos + 2 * len(cs) + 2 <= POOL_END
        b[pos:pos + 2 * len(cs)] = struct.pack('<%dH' % len(cs), *cs)
        struct.pack_into('<II', b, T + 8 * k, pos + D, len(cs))
        pos += 2 * len(cs) + 2
    for off, ko in ((0x64c870, '회초'), (0x64c878, '회말')):
        cs = kotext.codes(ko); b[off:off + 4] = struct.pack('<2H', *cs)
    return b

class Applier:
    def __init__(self):
        self.units = load_jsonl(os.path.join(ROOT, 'translation', 'units_sel.jsonl'))
        self.tr = load_translations()
        self.P, self.V = load_names()
        self.ND = name_dict(self.P)
        # 카드용: (성, 이름) 쌍 → 한국어, 성·이름별 사전
        self.PAIR = {}
        fc = collections.defaultdict(collections.Counter); gc = collections.defaultdict(collections.Counter)
        for (d, f, g), (kd, kf, kg) in self.P.items():
            if f: self.PAIR[(f, g)] = (kf, kg); fc[f][kf] += 1
            if g: gc[g][kg] += 1
        self.FD = {k: v.most_common(1)[0][0] for k, v in fc.items()}
        self.GD = {k: v.most_common(1)[0][0] for k, v in gc.items()}
        self.CX = dict(l.rstrip().split('\t') for l in open(os.path.join(ROOT, 'translation', 'names', 'card_extra.tsv'), encoding='utf-8') if '\t' in l)
        self.stats = collections.Counter()
        self.problems = []

    def ko_for(self, u):
        jp = u['jp']
        if u['src'] == 'P4525': return self.V.get(jp)
        if re.fullmatch(r'[ァ-ヺー・．Ａ-Ｚ]+', jp) and jp in self.ND: return self.ND[jp]
        ko = self.tr.get(jp)
        if ko is None or ko == jp: return None
        return ko

    def names_patch(self, b, src):
        b = bytearray(b)
        L = sorted([u for u in self.units if u['src'] == src], key=lambda u: u['off'])
        byoff = {u['off']: u for u in L}
        for u in L:
            if u['kind'] != 'name9': continue
            f = byoff.get(u['off'] + 0x12); g = byoff.get(u['off'] + 0x2a)
            key = (u['jp'], f['jp'] if f else '', g['jp'] if g else '')
            if key not in self.P: self.stats['name_missing'] += 1; continue
            for (off, cap), ko in zip(((u['off'], 9), (u['off'] + 0x12, 12), (u['off'] + 0x2a, 12)), self.P[key]):
                if off == u['off'] + 0x12 and not f: continue
                if off == u['off'] + 0x2a and not g: continue
                cs = kotext.codes(ko)[:cap]
                b[off:off + cap * 2] = struct.pack('<%dH' % cap, *(cs + [0] * (cap - len(cs))))
                self.stats['name_fields'] += 1
        return bytes(b)

    def card_names(self, b, src):
        """선수 카드: 0xAA 이름, 0xD2 성 (각 19자+FFFF) — 선수 DB 의 성/이름 쌍으로."""
        from charmap import CODE2CH
        jp = {}
        for off in (0xaa, 0xd2):
            a = struct.unpack_from('<20H', b, off)
            if 0xffff not in a: return
            jp[off] = ''.join(CODE2CH.get(c, '?') for c in a[:a.index(0xffff)])
        g, f = jp[0xaa], jp[0xd2]
        pair = self.PAIR.get((f, g))
        ko = {0xaa: pair[1] if pair else (self.GD.get(g) or self.CX.get(g) or self.ND.get(g)),
              0xd2: pair[0] if pair else (self.FD.get(f) or self.CX.get(f) or self.ND.get(f))}
        for off in (0xaa, 0xd2):
            if not jp[off]: continue
            if not ko[off]: self.stats['card_name_missing'] += 1; self.problems.append((src, hex(off), 'card name', jp[off])); continue
            cs = kotext.codes(ko[off])[:19]
            b[off:off + 40] = struct.pack('<20H', *(cs + [0xffff] + [0] * (19 - len(cs))))
            self.stats['card_names'] += 1

    def inplace(self, b, src):
        b = bytearray(b)
        iscard = any(u['kind'] == 'card' or u['off'] in (0xaa, 0xd2) for u in self.units if u['src'] == src) and src.startswith('P') and len(b) > 0x122
        if iscard: self.card_names(b, src)
        for u in [u for u in self.units if u['src'] == src and not u['kind'].startswith('name')]:
            if iscard and u['off'] in (0xaa, 0xd2): continue
            if 'cap2' in u: u = dict(u, cap=u['cap2'])
            ko = self.ko_for(u)
            if ko is None: continue
            cs = enc(ko, u.get('nl', 0x1ffe))
            if src == 'P4525': u = dict(u, cap=11)   # 호출명 24B 레코드
            if len(cs) > u['cap']:
                self.problems.append((src, u['id'], 'cap %d>%d' % (len(cs), u['cap']), ko)); cs = cs[:u['cap']]
            data = struct.pack('<%dH' % len(cs), *cs) + b'\xff\xff'
            b[u['off']:u['off'] + len(data)] = data
            # 남은 칸은 0 으로(원래 FFFF 뒤까지)
            end = u['off'] + u['cap'] * 2 + 2
            b[u['off'] + len(data):end] = bytes(end - u['off'] - len(data))
            self.stats['inplace'] += 1
        return bytes(b)

    def repack(self, b, src):
        b = bytearray(b)
        P = ptrs.pointers(bytes(b))
        T = collections.defaultdict(list)
        for p, t in P: T[t].append(p)
        L = sorted([u for u in self.units if u['src'] == src], key=lambda u: u['off'])
        items = []; noptr = []
        for u in L:
            o = u['off']
            tgt = o if o in T else None
            a = o - 2
            while tgt is None and a >= o - 16 and struct.unpack_from('<H', b, a)[0] == 0:
                if a in T: tgt = a
                a -= 2
            end = o
            while struct.unpack_from('<H', b, end)[0] != 0xffff: end += 2
            end += 2
            if tgt is None:
                noptr.append(u); continue
            ko = self.ko_for(u)
            cs = enc(ko, u.get('nl', 0x1ffe)) if ko is not None else list(struct.unpack_from('<%dH' % ((end - 2 - o) // 2), b, o))
            data = bytes(o - tgt) + struct.pack('<%dH' % len(cs), *cs) + b'\xff\xff'
            items.append((tgt, end, data, u, ko is not None))
        # 빈 슬롯: 각 문자열 [tgt, end) + 뒤따르는 0 패딩(다음 항목·포인터 대상 전까지)
        items.sort(key=lambda x: x[0])
        tset = set(T)
        slots = []
        for k, (tgt, end, data, u, _) in enumerate(items):
            nxt = items[k + 1][0] if k + 1 < len(items) else len(b)
            e2 = end
            while e2 + 2 <= nxt and e2 < len(b) - 1 and b[e2] == 0 and b[e2 + 1] == 0 and e2 not in tset: e2 += 2
            slots.append([tgt, e2])
        # 인접 슬롯 병합
        merged = []
        for s in slots:
            if merged and merged[-1][1] >= s[0]: merged[-1][1] = max(merged[-1][1], s[1])
            else: merged.append(list(s))
        for s0, s1 in merged: b[s0:s1] = bytes(s1 - s0)
        # 순서대로 채우기 (4바이트 정렬)
        seg = 0; pos = (merged[0][0] + 3) & ~3 if merged else 0
        for tgt, end, data, u, changed in items:
            while seg < len(merged) and pos + len(data) > merged[seg][1]:
                seg += 1
                if seg < len(merged): pos = (merged[seg][0] + 3) & ~3
            if seg >= len(merged):
                self.problems.append((src, u['id'], 'repack overflow')); return None
            b[pos:pos + len(data)] = data
            for p in T[tgt]: struct.pack_into('<I', b, p, 0x80000000 | pos)
            pos = (pos + len(data) + 3) & ~3
            self.stats['repacked' if changed else 'moved'] += 1
        # 포인터 없는 문자열: 제자리(원래 길이 이내)
        for u in noptr:
            ko = self.ko_for(u)
            if ko is None: continue
            cs = enc(ko, u.get('nl', 0x1ffe))
            n = 0
            while struct.unpack_from('<H', b, u['off'] + 2 * n)[0] != 0xffff: n += 1
            if len(cs) > n:
                self.problems.append((src, u['id'], 'noptr cap %d>%d' % (len(cs), n), ko)); cs = cs[:n]
            b[u['off']:u['off'] + 2 * n + 2] = struct.pack('<%dH' % len(cs), *cs) + b'\xff\xff' + bytes(2 * (n - len(cs)))
            self.stats['noptr_inplace'] += 1
        free = sum(s1 - s0 for s0, s1 in merged)
        used = sum(len(x[2]) for x in items)
        self.stats['repack_space_%s' % src] = '%d/%d' % (used, free)
        return bytes(b)

    def roster(self, b, src):
        """고정 폭(0 채움, 종료코드 없음) 이름 칸: translation/names/roster_hits.json."""
        if not hasattr(self, 'RH'):
            self.RH = json.load(open(os.path.join(ROOT, 'translation', 'names', 'roster_hits.json'), encoding='utf-8'))
        if src not in self.RH: return b
        b = bytearray(b)
        for o, jp, ko in self.RH[src]:
            n = len(jp); z = 0
            while z < 16 - n and o + 2 * (n + z) + 1 < len(b) and struct.unpack_from('<H', b, o + 2 * (n + z))[0] == 0: z += 1
            cap = n + max(0, z - 1) if src == 'P4095' else n + z
            if src == 'P4095': cap = min(cap, 12)
            cs = kotext.codes(ko)
            if len(cs) > cap: self.problems.append((src, o, 'roster cap %d>%d' % (len(cs), cap), ko)); cs = cs[:cap]
            b[o:o + 2 * cap] = struct.pack('<%dH' % cap, *(cs + [0] * (cap - len(cs))))
            self.stats['roster'] += 1
        return bytes(b)

    def pack(self, e, b):
        src = 'P%04d' % e['idx']
        if src in SCRIPTS: return self.script(b, src)
        return self.attr(self.roster(self._pack(e, b), src), src)

    def attr(self, b, src):
        """색 속성(코드 상위 4비트)이 섞인 문장: 문장 전체를 일반 글자로 번역해 덮어씀."""
        if not hasattr(self, 'AU'):
            p = os.path.join(ROOT, 'translation', 'attr_units.json')
            self.AU = collections.defaultdict(list)
            if os.path.exists(p):
                for u in json.load(open(p, encoding='utf-8')): self.AU[u['src']].append(u)
        if not hasattr(self, 'FX'):
            self.FX = collections.defaultdict(list)
            for u in json.load(open(os.path.join(ROOT, 'translation', 'fixed_1fff.json'), encoding='utf-8')): self.FX[u['src']].append(u)
        if src in self.FX:
            b = bytearray(b)
            for u in self.FX[src]:
                cs = kotext.codes(u['ko'])[:u['n']]
                b[u['off']:u['off'] + 2 * len(cs)] = struct.pack('<%dH' % len(cs), *cs)
                self.stats['fixed'] += 1
            b = bytes(b)
        if src not in self.AU: return b
        b = bytearray(b)
        for u in self.AU[src]:
            ko = self.tr.get(u['jp'])
            if ko is None or ko == u['jp']: continue
            cs = enc(ko, 0x1ffe)
            if len(cs) > u['n']: self.problems.append((src, u['off'], 'attr cap %d>%d' % (len(cs), u['n']), ko)); cs = cs[:u['n']]
            b[u['off']:u['off'] + 2 * u['n'] + 2] = struct.pack('<%dH' % len(cs), *cs) + b'\xff\xff' + bytes(2 * (u['n'] - len(cs)))
            self.stats['attr'] += 1
        return bytes(b)

    def script(self, b, src):
        """바이트코드 대사 스크립트: translation/script/out 의 번역을 같은 길이로 덮어씀."""
        import script
        if not hasattr(self, 'SC'):
            self.SC = {}
            for p in glob.glob(os.path.join(ROOT, 'translation', 'script', 'jobs', '*.jsonl')):
                J = {x['id']: x['jp'] for x in load_jsonl(p)}
                q = p.replace(os.sep + 'jobs' + os.sep, os.sep + 'out' + os.sep).replace('/jobs/', '/out/')
                if os.path.exists(q):
                    for o in load_jsonl(q):
                        if o.get('id') in J: self.SC[J[o['id']]] = o['ko']
        U = json.load(open(os.path.join(ROOT, 'translation', 'script', 'units_%s.json' % src), encoding='utf-8'))
        todo = []
        for u in U:
            if u['jp'] not in self.SC: continue
            ko = self.SC[u['jp']]; jp = u['jp']
            # 원문 맨 앞의 표식 한 글자(바로 뒤가 태그·공백) 는 명령 인자일 수 있으므로 보존
            if len(jp) > 1 and jp[1] in '{　' and '一' <= jp[0] <= '鿿' and not ko.startswith(jp[0]):
                c0 = struct.unpack_from('<H', b, u['off'])[0]
                ko = '{%04X}' % c0 + ko
            # 넘치면 공백부터 줄이고, 그래도 넘치면 끝 태그 앞 글자를 자름
            while len(script.encode(ko)) > u['n'] and '　' in ko[1:]:
                i = ko.rindex('　'); ko = ko[:i] + ko[i + 1:]
            while len(script.encode(ko)) > u['n']:
                m = re.search(r'[^\}](?=(\{[0-9A-F]{4}\})*$)', ko)
                if not m: break
                ko = ko[:m.start()] + ko[m.end():]
            todo.append((u['off'], u['n'], ko))
        nb, probs = script.patch(b, todo)
        for p in probs: self.problems.append((src, p[0], 'script len %d>%d' % (p[1], p[2]), p[3]))
        self.stats['script_' + src] = '%d/%d' % (len(todo), len(U))
        return nb

    def _pack(self, e, b):
        src = 'P%04d' % e['idx']
        if src in NAME_DBS: return self.names_patch(b, src)
        if src in REPACK:
            r = self.repack(b, src)
            return r if r is not None else self.inplace(b, src)
        return self.inplace(b, src)

    def elf(self, b):
        import namegrid
        b = bytearray(self.attr(self.inplace(b, 'ELF'), 'ELF'))
        b = highlight(b)
        # 「○か×ボタン」의 か → 나 (버튼 기호 사이 한 글자)
        if struct.unpack_from('<H', b, 0x66cb92)[0] == 0x124:
            struct.pack_into('<H', b, 0x66cb92, kotext.codes('나')[0])
        return namegrid.patch_elf(bytes(b))

    def sources(self):
        rh = json.load(open(os.path.join(ROOT, 'translation', 'names', 'roster_hits.json'), encoding='utf-8'))
        au = json.load(open(os.path.join(ROOT, 'translation', 'attr_units.json'), encoding='utf-8'))
        return sorted({u['src'] for u in self.units} | set(rh) | SCRIPTS | {u['src'] for u in au} | {'P1830', 'P3698'})

if __name__ == '__main__':
    A = Applier()
    print(len(A.tr), 'translations', len(A.P), 'players', len(A.V), 'voice')
