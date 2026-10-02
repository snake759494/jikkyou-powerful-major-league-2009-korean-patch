"""ISO9660 읽기 도우미 (2048B 섹터 DVD ISO)."""
import os, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ISO = os.path.join(ROOT, 'Jikkyou Powerful Major League 2009 (Japan).iso')

def read(lba, size, iso=ISO):
    with open(iso, 'rb') as f:
        f.seek(lba * 2048); return f.read(size)

def walk(iso=ISO):
    """(경로, lba, 크기, 레코드 위치) 목록."""
    pvd = read(16, 2048, iso)
    rlba, rsize = struct.unpack_from('<I', pvd, 156 + 2)[0], struct.unpack_from('<I', pvd, 156 + 10)[0]
    out = []
    def rec(lba, size, path):
        d = read(lba, size, iso); i = 0
        while i < size:
            n = d[i]
            if n == 0:
                i = (i // 2048 + 1) * 2048; continue
            flba, fsz = struct.unpack_from('<I', d, i + 2)[0], struct.unpack_from('<I', d, i + 10)[0]
            fl = d[i + 25]; nl = d[i + 32]; name = d[i + 33:i + 33 + nl]
            if name not in (b'\0', b'\1'):
                nm = name.decode('latin1').split(';')[0]
                if fl & 2: rec(flba, fsz, path + nm + '/')
                else: out.append((path + nm, flba, fsz, lba * 2048 + i))
            i += n
    rec(rlba, rsize, '')
    return out

if __name__ == '__main__':
    for p, l, s, r in walk(): print(f'{l:8d} {s:11d} {p}')
