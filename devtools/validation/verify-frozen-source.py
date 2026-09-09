"""Check packaged project bytecode/assets against the delivered source."""
from pathlib import Path
import json, types
from PyInstaller.archive.readers import CArchiveReader
ROOT=Path(__file__).resolve().parents[1]
release=ROOT/'release'/f"LTE-Control-Plane-Simulator-v{(ROOT/'VERSION').read_text().strip()}-win64"
def normalized(code):
    return code.replace(co_filename='',co_consts=tuple(normalized(x) if isinstance(x,types.CodeType) else x for x in code.co_consts))
results=[]
for exe in release.glob('*.exe'):
    archive=CArchiveReader(str(exe))
    pyz=archive.open_embedded_archive('PYZ.pyz')
    assert not any('libsrtp' in name.lower() for name in list(archive.toc)+list(pyz.toc))
    checked=[]
    for name in pyz.toc:
        if name=='lte_sim' or name.startswith('lte_sim.'):
            source=ROOT/'src'/Path(*name.split('.'))
            source=source/'__init__.py' if source.is_dir() else source.with_suffix('.py')
            assert source.is_file(),str(source)
            assert normalized(compile(source.read_bytes(),str(source),'exec'))==normalized(pyz.extract(name)),name
            checked.append(name)
    assets=[]
    for name in archive.toc:
        if name.startswith('lte_sim\\web\\'):
            assert archive.extract(name)==(ROOT/'src'/Path(name)).read_bytes(),name
            assets.append(name)
    results.append(dict(exe=exe.name,modules=len(checked),webAssets=len(assets),sourceMatch='PASS',noLibsrtp='PASS'))
print(json.dumps(results,indent=2))
