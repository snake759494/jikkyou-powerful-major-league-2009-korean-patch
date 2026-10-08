"""PCSX2 16:9 와이드 패치(pnach) 생성.
PCSX2 패치 DB의 원본판 패치(SLPM-55155_3E8C9B7D, 작성자 Arapapa)는 원본 ELF CRC 에만 적용된다.
한글판은 ELF 문자열이 바뀌어 CRC 가 달라지므로, 코드 주소가 같은지 확인한 뒤 한글판 CRC 이름으로 다시 만든다.
사용: python tools/widescreen.py <한글판 ISO>  → widescreen/SLPM-55155_<CRC>.pnach"""
import os, sys, re, struct
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iso
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
D = 0xFFE80
# Arapapa 패치: 게임 화면 가로 시야(0x44200000 → 0x44555555, 3/4 배) — 원래 값 주석 포함
PATCH = [(0x001315fc, 0x3c024455, 0x3c024420), (0x00131600, 0x34425555, 0x44820800),
         (0x00131604, 0x44820800, 0x3c0243f0), (0x00131608, 0x3c0243f0, 0x44911000),
         (0x0013160c, 0x44911000, 0x00000000)]

def elf_crc(b):
    return int(np.bitwise_xor.reduce(np.frombuffer(b[:len(b) // 4 * 4], '<u4')))

def main(path):
    files = {p: (l, s) for p, l, s, r in iso.walk(path)}
    lba, size = files['SLPM_551.55']
    with open(path, 'rb') as f:
        f.seek(lba * 2048); elf = f.read(size)
    for a, new, old in PATCH:
        cur = struct.unpack_from('<I', elf, a - D)[0]
        assert cur == old, 'code mismatch at %08x: %08x' % (a, cur)
    crc = elf_crc(elf)
    lines = ['gametitle=Jikkyou Powerful Major League 2009 (J)(SLPM-55155) [Korean patch]',
             '', '// 16:9 widescreen - ported from PCSX2 patch DB (SLPM-55155_3E8C9B7D, author Arapapa)',
             'gsaspectratio=16:9', '']
    lines += ['patch=1,EE,%08x,word,%08x //%08x' % p for p in PATCH]
    os.makedirs(os.path.join(ROOT, 'widescreen'), exist_ok=True)
    out = os.path.join(ROOT, 'widescreen', 'SLPM-55155_%08X.pnach' % crc)
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print(out)

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'Jikkyou Powerful Major League 2009 (Japan) (Korean).iso'))
