"""원본 ISO → 한글판 ISO. 현재: 폰트 팩 제자리 교체 + ELF 문자열 패치(translation/elf_*.json)."""
import os, sys, shutil, struct, json, tempfile, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iso, proj
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SRC = iso.ISO
DST = os.path.join(ROOT, 'Jikkyou Powerful Major League 2009 (Japan) (Korean).iso')
FILES = {p: (l, s) for p, l, s, r in iso.walk()}

def write_file_bytes(f, name, off, data):
    lba, size = FILES[name]
    assert off + len(data) <= size, name
    f.seek(lba * 2048 + off); f.write(data)

def pack_offset(name):
    d, ents = proj.load()
    for e in ents:
        if e['name'] == name: return proj.DATA + e['off'] * 0x800, e['size']
    raise KeyError(name)

def main(patches_elf, packs):
    if not os.path.exists(DST) or os.path.getsize(DST) != os.path.getsize(SRC):
        shutil.copyfile(SRC, DST)
    with open(DST, 'r+b') as f:
        # ELF 는 원본에서 새로 만든 전체를 덮어씀
        elf = bytearray(open(os.path.join(ROOT, 'work', 'SLPM_551.55'), 'rb').read())
        for off, data in patches_elf: elf[off:off + len(data)] = data
        write_file_bytes(f, 'SLPM_551.55', 0, bytes(elf))
        for name, data in packs.items():
            o, sz = pack_offset(name)
            assert len(data) <= ((sz + 0x7ff) & ~0x7ff), name
            write_file_bytes(f, 'PROJECT.BIN', o, data)
    print('built', DST)

def full():
    import apply, collections
    A = apply.Applier()
    d, ents = proj.load(); E = {e['idx']: e for e in ents}
    elf = A.elf(open(os.path.join(ROOT, 'work', 'SLPM_551.55'), 'rb').read())
    packs = {'ScsComMainMonPM4.pack': open(os.path.join(ROOT, 'work', 'font_ko.pack'), 'rb').read()}
    for src in A.sources():
        if src == 'ELF': continue
        e = E[int(src[1:])]
        b = open(os.path.join(ROOT, 'work', 'pack', e['name']), 'rb').read()
        nb = A.pack(e, b)
        assert len(nb) == len(b)
        if nb != b: packs[e['name']] = nb
    import tex_apply
    packs = tex_apply.apply_all(packs)
    json.dump(A.problems, open(os.path.join(ROOT, 'work', 'build_problems.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    if A.problems:
        raise RuntimeError(f'Build stopped: {len(A.problems)} translation problems')
    # Always start from the original: removed patches must not survive a rebuild.
    # Publish only after read-back verification; a failure preserves the last ISO.
    fd, staged = tempfile.mkstemp(prefix='korean-build-', suffix='.iso', dir=ROOT)
    os.close(fd)
    shutil.copyfile(SRC, staged)
    report = {'packs': {}, 'stats': dict(A.stats), 'problems': []}
    with open(staged, 'r+b') as f:
        write_file_bytes(f, 'SLPM_551.55', 0, elf)
        writes = [('SLPM_551.55', 0, elf)]
        for name, data in packs.items():
            o, sz = pack_offset(name)
            assert len(data) == sz, (name, len(data), sz)
            write_file_bytes(f, 'PROJECT.BIN', o, data)
            writes.append(('PROJECT.BIN', o, data))
            report['packs'][name] = {'offset': o, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        f.flush()
        os.fsync(f.fileno())
        for name, off, expected in writes:
            f.seek(FILES[name][0] * 2048 + off)
            assert f.read(len(expected)) == expected, (name, off)
    assert os.path.getsize(staged) == os.path.getsize(SRC)
    os.replace(staged, DST)
    report['verified_writes'] = len(writes)
    with open(os.path.join(ROOT, 'work', 'build_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(dict(A.stats))
    print('problems', len(A.problems))
    for p in A.problems[:40]: print(' ', p)
    json.dump(A.problems, open(os.path.join(ROOT, 'work', 'build_problems.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

if __name__ == '__main__':
    full()
