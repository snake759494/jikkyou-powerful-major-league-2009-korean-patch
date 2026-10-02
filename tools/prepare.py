"""Extract build inputs from the verified original ISO into a new work directory."""
import json
from pathlib import Path
import shutil
import iso
import proj
from apply_release import verify

ROOT = Path(__file__).resolve().parents[1]


def main():
    work = ROOT / 'work'
    if work.exists():
        raise FileExistsError('work already exists; use a clean checkout for preparation')
    source = Path(iso.ISO)
    manifest = json.loads((ROOT / 'release_manifest.json').read_text(encoding='utf-8'))
    verify(source, manifest['source'])
    entries = {name: (lba, size) for name, lba, size, _ in iso.walk()}
    required = ('PROJECT.BIN', 'SLPM_551.55')
    for name in required:
        if name not in entries:
            raise ValueError('Missing ISO file: ' + name)
    work.mkdir()
    with source.open('rb') as src:
        for name in required:
            lba, remaining = entries[name]
            src.seek(lba * 2048)
            with (work / name).open('xb') as dst:
                while remaining:
                    block = src.read(min(8 << 20, remaining))
                    if not block:
                        raise EOFError(name)
                    dst.write(block)
                    remaining -= len(block)
    _, packs = proj.load(str(work / 'PROJECT.BIN'))
    (work / 'pack').mkdir()
    with (work / 'PROJECT.BIN').open('rb') as src:
        for entry in packs:
            name = entry['name']
            if Path(name).name != name:
                raise ValueError('Invalid pack name')
            data = proj.read(entry, src)
            if len(data) != entry['size'] or data[:8] != b'PACKPS2 ':
                raise ValueError('Invalid pack: ' + name)
            (work / 'pack' / name).write_bytes(data)
    (work / 'tex').mkdir()
    shutil.copyfile(ROOT / 'metadata/kanji_plan.json', work / 'kanji_plan.json')
    shutil.copyfile(ROOT / 'metadata/texture_catalog.json', work / 'tex/catalog.json')
    print('Prepared packs:', len(packs))


if __name__ == '__main__':
    main()
