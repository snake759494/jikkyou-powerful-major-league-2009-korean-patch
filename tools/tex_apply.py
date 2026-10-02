"""그림 글자 명세(translation/tex/*.json) 적용 → {팩이름: 바이트}.
명세: {"hash": ..., "items": [{"box": [x0,y0,x1,y1], "ko": "...", "weight": "heavy"}]}
같은 텍스처(해시)가 여러 팩에 있으면 모두 교체."""
import os, sys, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texedit, proj
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
def apply_all(packs):
    """packs: {팩이름: bytes} (이미 수정된 것) 를 받아 텍스처 명세를 덧씌워 돌려준다."""
    d, ents = proj.load(); E = {e['idx']: e for e in ents}
    cat = json.load(open(os.path.join(ROOT, 'work', 'tex', 'catalog.json')))
    n = 0
    for p in sorted(glob.glob(os.path.join(ROOT, 'translation', 'tex', '*.json'))):
        spec = json.load(open(p, encoding='utf-8'))
        items = [it for it in spec.get('items', []) if it.get('ko')]
        if not items: continue
        for pi, off in cat[spec['hash']]['refs']:
            name = E[pi]['name']
            b = bytearray(packs.get(name) or open(os.path.join(ROOT, 'work', 'pack', name), 'rb').read())
            idx, pal, meta = texedit.load(b, off)
            if not pal[:, 3].any(): continue   # 팔레트를 찾지 못한 참조는 건너뜀
            bg = texedit.background(idx, pal)
            orig = idx.copy()
            import texclean
            texclean.paint_all(idx, pal, orig, items, bg)
            texedit.store(b, off, idx)
            packs[name] = bytes(b); n += 1
    n += shadows(packs, E, cat)
    import hudfont
    n += hudfont.patch(packs)
    print('textures patched', n)
    return packs

# 글자 모양을 그대로 본뜬 그림자 텍스처: (글자 해시, 그림자 해시, 덮을 세로 범위, 두께, dx, dy)
SHADOWS = [('713f653c7405', '222a2050ceb2', (0, 320), 1, 2, 3)]

def shadows(packs, E, cat):
    import numpy as np
    from scipy import ndimage
    n = 0
    for th, sh, (ya, yb), r, dx, dy in SHADOWS:
        pi, toff = cat[th]['refs'][0]
        name = E[pi]['name']
        tb = packs.get(name) or open(os.path.join(ROOT, 'work', 'pack', name), 'rb').read()
        ti, tp, _ = texedit.load(tb, toff)
        ta = tp[ti][..., 3].astype(np.float32)
        a = ndimage.grey_dilation(ta, size=(2 * r + 1, 2 * r + 1)) if r else ta
        a = np.roll(np.roll(a, dy, 0), dx, 1)
        for pj, soff in cat[sh]['refs']:
            sname = E[pj]['name']
            b = bytearray(packs.get(sname) or open(os.path.join(ROOT, 'work', 'pack', sname), 'rb').read())
            si, sp, _ = texedit.load(b, soff)
            so = sp[si][..., 3] > 40
            col = np.median(sp[si][so][:, :3], 0) if so.any() else np.array([36, 81, 140])
            reg = np.zeros((yb - ya, si.shape[1], 4), np.float32)
            reg[..., :3] = col; reg[..., 3] = a[ya:yb, :si.shape[1]]
            q = texedit.quantize(reg, sp)
            bgi = texedit.background(si, sp)
            q[reg[..., 3] < 4] = bgi
            si[ya:yb] = q
            texedit.store(b, soff, si)
            packs[sname] = bytes(b); n += 1
    return n
