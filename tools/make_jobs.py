"""units_sel.jsonl → 번역 작업 파일.
 - translation/jobs/NNN.jsonl : 일반 문장 (고유 문장 단위)
 - translation/names/players.jsonl : 선수 DB (표시명/성/이름 묶음)
 - translation/names/voice.jsonl : 실황 호출명 목록(P4525)"""
import json, os, re, collections
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
REPACK = {'P1696', 'P3779', 'P1693', 'P1692', 'P1695', 'P1694', 'P1807', 'P1698', 'P1674', 'P1699', 'P4065', 'P1697', 'P4579'}
NAME_DBS = {'P4095', 'P4087', 'P3704', 'P3614', 'P3613'}
def cells(s): return len(re.sub(r'\{[0-9A-F]{4}\}', 'X', s))   # 줄바꿈 코드도 1칸
def width(s): return max(len(re.sub(r'\{[0-9A-F]{4}\}', 'X', x)) for x in re.split(r'\n|\{D000\}|\{1FFE\}', s))
def is_kata_name(s): return re.fullmatch(r'[ァ-ヺー・．Ａ-Ｚ]+', s) is not None
def main(per_job=400):
    S = [json.loads(l) for l in open(os.path.join(ROOT, 'translation', 'units_sel.jsonl'), encoding='utf-8')]
    os.makedirs(os.path.join(ROOT, 'translation', 'jobs'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'translation', 'names'), exist_ok=True)
    # 선수 DB
    players = []
    by = collections.defaultdict(list)
    for u in S: by[u['src']].append(u)
    for src in NAME_DBS:
        L = sorted(by[src], key=lambda u: u['off'])
        i = 0
        while i < len(L):
            u = L[i]
            if u['kind'] == 'name9':
                rec = {'src': src, 'disp': u['jp'], 'fam': '', 'giv': ''}
                for v in L[i + 1:i + 3]:
                    if v['off'] == u['off'] + 0x12: rec['fam'] = v['jp']
                    if v['off'] == u['off'] + 0x2a: rec['giv'] = v['jp']
                players.append(rec)
            i += 1
    uniq = {}
    for p in players:
        k = (p['disp'], p['fam'], p['giv'])
        if k not in uniq: uniq[k] = dict(id=len(uniq), src=p['src'], disp=p['disp'], fam=p['fam'], giv=p['giv'])
    with open(os.path.join(ROOT, 'translation', 'names', 'players.jsonl'), 'w', encoding='utf-8') as f:
        for v in uniq.values(): f.write(json.dumps(v, ensure_ascii=False) + '\n')
    # 실황 호출명
    voice = []
    seen = set()
    for u in sorted(by['P4525'], key=lambda u: u['off']):
        if u['jp'] not in seen: seen.add(u['jp']); voice.append(dict(id=len(voice), jp=u['jp'], cap=11))   # 24B 레코드: 11자+FFFF
    with open(os.path.join(ROOT, 'translation', 'names', 'voice.jsonl'), 'w', encoding='utf-8') as f:
        for v in voice: f.write(json.dumps(v, ensure_ascii=False) + '\n')
    # 일반 문장
    text = collections.OrderedDict()
    order = sorted([u for u in S if u['src'] not in NAME_DBS and u['src'] != 'P4525'], key=lambda u: (u['src'] != 'ELF', u['src'], u['off']))
    for u in order:
        s = u['jp']
        mode = 'soft' if u['src'] in REPACK else ('card' if u['kind'] == 'card' else 'strict')
        if s not in text: text[s] = dict(jp=s, cap=u.get('cap2', u['cap']), mode=mode, w=width(s), srcs={u['src']})
        else:
            t = text[s]; t['srcs'].add(u['src'])
            if mode == 'strict' or t['mode'] == 'strict':
                t['cap'] = min(t['cap'] if t['mode'] == 'strict' else 999, u.get('cap2', u['cap'])); t['mode'] = 'strict'
    items = list(text.values())
    for i, t in enumerate(items):
        t['id'] = i; t['srcs'] = sorted(t['srcs'])
        if t['mode'] == 'soft': t['cap'] = max(cells(t['jp']), 1)
    jobs = []
    cur = []; chars = 0
    for t in items:
        cur.append(t); chars += len(t['jp'])
        if chars >= 6000 or len(cur) >= per_job:
            jobs.append(cur); cur = []; chars = 0
    if cur: jobs.append(cur)
    for j, L in enumerate(jobs):
        with open(os.path.join(ROOT, 'translation', 'jobs', '%03d.jsonl' % j), 'w', encoding='utf-8') as f:
            for t in L: f.write(json.dumps(dict(id=t['id'], jp=t['jp'], cap=t['cap'], mode=t['mode'], w=t['w'], src=t['srcs'][0]), ensure_ascii=False) + '\n')
    json.dump({t['jp']: t['id'] for t in items}, open(os.path.join(ROOT, 'translation', 'text_ids.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print('players', len(uniq), 'voice', len(voice), 'texts', len(items), 'jobs', len(jobs), 'chars', sum(len(t['jp']) for t in items))
    print('strict', sum(1 for t in items if t['mode'] == 'strict'), 'katakana-name-like', sum(1 for t in items if is_kata_name(t['jp'])))
if __name__ == '__main__': main()
