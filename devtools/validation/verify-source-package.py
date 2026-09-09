"""Verify/extract a fresh source ZIP, then run its own self_test.py."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, os, subprocess, sys, zipfile
parser=argparse.ArgumentParser()
parser.add_argument('archive',type=Path)
parser.add_argument('destination',type=Path,help='Fresh directory; existing targets are refused')
args=parser.parse_args()
archive=args.archive.resolve();dest=args.destination.resolve()
if dest.exists(): raise SystemExit('Refusing existing extraction destination')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None, 'CRC error'
    names=z.namelist()
    assert len(names)==len(set(names))
    for name in names:
        path=PurePosixPath(name)
        assert not path.is_absolute() and '..' not in path.parts and '\\' not in name
        rel_parts = path.parts[1:]  # archive always has one versioned top-level folder
        assert not any(p in {'__pycache__','.pytest_cache','.git','node_modules'} for p in rel_parts)
        assert not rel_parts or rel_parts[0] not in {'var','release','build','dist','.venv','.venv-build'}
        assert path.suffix not in {'.pyc','.pyo','.tmp','.exe'}
    z.extractall(dest)
version=(dest / next(name for name in os.listdir(dest) if name.startswith('lte-control-plane-sim-engineering-v')) / 'VERSION').read_text().strip()
root=dest/f'lte-control-plane-sim-engineering-v{version}'
manifest_path=root/'packaging'/'SOURCE-MANIFEST.json'
manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}==set(manifest)|{'packaging/SOURCE-MANIFEST.json'}
for name,expected in manifest.items():
    data=(root/name).read_bytes()
    assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256'],name
assert (root/'docs'/'README-说明书.md').is_file(), 'Chinese README manual filename missing'
env=os.environ.copy();env['PYTHONPATH']=str(root/'src');env['PYTHONIOENCODING']='utf-8'
self_test = root / 'devtools' / 'validation' / 'self_test.py'
if self_test.is_file():
    command=[sys.executable,'devtools/validation/self_test.py']
    check_mode='FULL_SELF_TEST'
else:
    # A --without-devtools package is intentionally missing pytest/self-test.
    # Verify that the runtime source itself compiles and imports cleanly.
    command=[sys.executable,'-c',
        'import compileall; assert compileall.compile_dir("src", quiet=1); '
        'from lte_sim.state import default_state; '
        'from lte_sim.security_engine.service import probe_security_core; '
        'assert default_state()["version"]; assert probe_security_core()["verified"]; '
        'print("RUNTIME SOURCE CHECK PASS")']
    check_mode='RUNTIME_SOURCE_CHECK'
run=subprocess.run(command,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
archive.with_suffix('.acceptance.log').write_text(run.stdout,encoding='utf-8')
result=dict(archive=archive.name,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=len(manifest)+1,
    manifest='PASS',chineseFilenames='PASS',crc='PASS',cleanSource='PASS',verificationMode=check_mode,
    extractedSelfTestExitCode=run.returncode,extractionRoot=str(root))
archive.with_suffix('.acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False));print(run.stdout)
raise SystemExit(run.returncode)
