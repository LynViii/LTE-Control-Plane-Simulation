from __future__ import annotations

from pathlib import Path

root = Path(__file__).resolve().parents[2]
version = (root / "VERSION").read_text(encoding="utf-8").strip()
parts = [int(part) for part in version.split(".")]
while len(parts) < 4:
    parts.append(0)
version_tuple = tuple(parts[:4])
target = root / "packaging" / "version-info.txt"
text = f'''VSVersionInfo(\n  ffi=FixedFileInfo(filevers={version_tuple}, prodvers={version_tuple}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),\n  kids=[\n    StringFileInfo([StringTable('040904B0', [\n      StringStruct('CompanyName', 'LTE Control Plane Simulator'),\n      StringStruct('FileDescription', 'LTE Control Plane Simulator'),\n      StringStruct('FileVersion', '{version}'),\n      StringStruct('InternalName', 'LTE-Control-Plane-Simulator'),\n      StringStruct('OriginalFilename', 'LTE-Control-Plane-Simulator.exe'),\n      StringStruct('ProductName', 'LTE Control Plane Simulator'),\n      StringStruct('ProductVersion', '{version}')\n    ])]),\n    VarFileInfo([VarStruct('Translation', [1033, 1200])])\n  ]\n)\n'''
target.write_text(text, encoding="utf-8")
print(target)
