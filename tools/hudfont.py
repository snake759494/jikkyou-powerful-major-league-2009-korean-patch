"""경기 HUD 가타카나 글꼴(243d955fce97, 16x16 칸) → 한글 음절로 다시 그림.
구종명 등이 가타카나 칸 번호로 조합되므로 칸마다 대응 음절을 그린다."""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texedit, proj
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
HASH = '243d955fce97'
K = ('아이우에오카키크케코사시스세소타치츠테트나니누네노하히프헤호마미무메모야유요라리루레로와오ㄴ'
     '가기그게고자지즈제조다지즈데도바비부베보파피프페포아이우에오야유요ㅅ부')
MAP = {13 + i: ch for i, ch in enumerate(K)}
MAP[122] = '-'
def cell_img(ch):
    S = 8
    f = ImageFont.truetype(os.path.join(ROOT, 'NanumSquareNeo-eHv.ttf'), 13 * S)
    im = Image.new('L', (16 * S, 16 * S), 0); dr = ImageDraw.Draw(im)
    bx = dr.textbbox((0, 0), ch, font=f); w, h = bx[2] - bx[0], bx[3] - bx[1]
    dr.text(((14 * S - w) // 2 - bx[0], (16 * S - h) // 2 - bx[1]), ch, font=f, fill=255)
    a = np.asarray(im, np.float32) / 255
    core = a > 0.5
    ring = ndimage.distance_transform_edt(~core) <= 1.3 * S
    fc = core.reshape(16, S, 16, S).mean((1, 3)); rc = ring.reshape(16, S, 16, S).mean((1, 3))
    out = np.zeros((16, 16), np.uint8)
    out[rc > 0.15] = 4; out[rc > 0.5] = 7
    lv = np.clip(np.round(9 + fc * 6), 9, 15).astype(np.uint8)
    out = np.where(fc > 0.25, lv, out)
    return out
def patch(packs):
    d, ents = proj.load(); E = {e['idx']: e for e in ents}
    cat = json.load(open(os.path.join(ROOT, 'work', 'tex', 'catalog.json')))
    n = 0
    for pi, off in cat[HASH]['refs']:
        name = E[pi]['name']
        b = bytearray(packs.get(name) or open(os.path.join(ROOT, 'work', 'pack', name), 'rb').read())
        idx, pal, m = texedit.load(b, off)
        for c, ch in MAP.items():
            x, y = (c % 8) * 16, (c // 8) * 16
            idx[y:y + 16, x:x + 16] = cell_img(ch)
        texedit.store(b, off, idx); packs[name] = bytes(b); n += 1
    return n
if __name__ == '__main__':
    d, ents = proj.load(); E = {e['idx']: e for e in ents}
    cat = json.load(open(os.path.join(ROOT, 'work', 'tex', 'catalog.json')))
    packs = {}; patch(packs)
    pi, off = cat[HASH]['refs'][0]
    idx, pal, m = texedit.load(packs[E[pi]['name']], off)
    r = pal[idx].astype(np.float32); a = np.clip(r[..., 3:] * 2, 0, 255) / 255
    Image.fromarray((r[..., :3] * a + 60 * (1 - a)).astype(np.uint8)).resize((512, 1024), Image.NEAREST).save(os.path.join(ROOT, 'work', 'hudfont_ko.png'))
