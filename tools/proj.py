"""PROJECT.BIN (Konami) 구조.
헤더 0x2c000: [0,0,개수,0] 뒤 (레코드번호, 섹터오프셋) 쌍. 데이터 = 0x6a800 + 오프셋*0x800.
레코드표 0x6800: 28B [0, ?, 섹터수, 0x800, 0, 0, 크기]. 이름표 0x35800: NUL 구분, 쌍 순서와 같음.
각 파일은 'PACKPS2 ' 0x20B 헤더 + 본문."""
import struct, os
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PB = os.path.join(ROOT, 'work', 'PROJECT.BIN')
DATA = 0x6a800

def load(path=PB):
    with open(path, 'rb') as f: d = f.read(DATA)
    n = struct.unpack_from('<I', d, 0x2c008)[0]
    names = [x.decode() for x in d[0x35800:DATA].split(b'\0') if x][:n]
    ents = []
    for i in range(n):
        rec, off = struct.unpack_from('<2I', d, 0x2c010 + i * 8)
        r = struct.unpack_from('<7I', d, 0x6800 + rec * 28)
        ents.append(dict(idx=i, rec=rec, off=off, name=names[i].split('/')[-1], sec=r[2], size=r[6]))
    return d, ents

def read(e, f):
    f.seek(DATA + e['off'] * 0x800); return f.read(e['size'])

if __name__ == '__main__':
    d, ents = load()
    out = os.path.join(ROOT, 'work', 'pack'); os.makedirs(out, exist_ok=True)
    with open(PB, 'rb') as f:
        bad = 0
        for e in ents:
            b = read(e, f)
            if b[:8] != b'PACKPS2 ': bad += 1; print('bad', e)
            open(os.path.join(out, e['name']), 'wb').write(b)
    print(len(ents), 'bad', bad, 'dupnames', len(ents) - len({e['name'] for e in ents}))
