"""한글 폰트 생성: 0x2C2~ 에 KS X 1001 한글 2350자(NanumSquareNeo ExtraBold), 남는 한자칸은 비움.
결과: work/font_ko.pack (원본 PACK 헤더 유지, 폰트2는 같은 오프셋 0x68200)."""
import sys, os, struct, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pfont
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
HSTART = 0x2C2
HANGUL = [bytes([0xB0 + i // 94, 0xA1 + i % 94]).decode('cp949') for i in range(2350)]
FONT = os.path.join(ROOT, 'NanumSquareNeo-dEb.ttf'); SIZE = 16

def hcode(ch): return HSTART + HANGUL.index(ch)

def render(ch, font):
    im = Image.new('L', (22 * 4, 28 * 4), 0); dr = ImageDraw.Draw(im)
    f4 = font
    x0, y0, x1, y1 = dr.textbbox((0, 0), ch, font=f4)
    w, h = x1 - x0, y1 - y0
    # 한자 칸(가로 0~14, 세로 0~16)에 가운데 정렬 (4배 해상도에서 그린 뒤 축소)
    ox = (15 * 4 - w) // 2 - x0; oy = (17 * 4 - h) // 2 - y0
    dr.text((ox, oy), ch, font=f4, fill=255)
    a = np.asarray(im.resize((22, 28), Image.LANCZOS), np.float32) / 255
    q = np.clip(np.round(a * 15 * 1.08), 0, 15).astype(np.uint8)
    return q

def build():
    src = open(os.path.join(ROOT, 'work', 'pack', 'ScsComMainMonPM4.pack'), 'rb').read()
    d = src[0x20:]
    (o1, cnt, offs, base), (o2, *_ ) = pfont.fonts(d)
    font = ImageFont.truetype(FONT, SIZE * 4)
    import namegrid
    ov = namegrid.glyph_overrides()
    glyphs = []
    for c in range(cnt):
        if c in ov:
            glyphs.append(pfont.encode(pfont.from_pixels(render(ov[c], font))))
        elif HSTART <= c < HSTART + 2350:
            glyphs.append(pfont.encode(pfont.from_pixels(render(HANGUL[c - HSTART], font))))
        elif HSTART + 2350 <= c < 0xE57:
            glyphs.append(pfont.encode(np.zeros((28, 11), np.uint8)))
        else:
            b, used = pfont.decode(d[base + offs[c]:]); glyphs.append(d[base + offs[c]: base + offs[c] + used])
    body = bytearray(); newoffs = []
    for g in glyphs: newoffs.append(len(body)); body += g
    f1 = d[:4] + struct.pack('<%dI' % cnt, *newoffs) + body
    assert len(f1) <= o2, (hex(len(f1)), hex(o2))
    out = src[:0x20] + f1 + bytes(o2 - len(f1)) + d[o2:]
    assert len(out) == len(src)
    open(os.path.join(ROOT, 'work', 'font_ko.pack'), 'wb').write(out)
    print('font1 size', hex(len(f1)), 'limit', hex(o2))

if __name__ == '__main__':
    build()
