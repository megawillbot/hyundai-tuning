r"""Paddock pops 'loud': nodhp image + later ignition in the cut (see notes.md, 2026-09-19).

Measured (tools/ram_logger.py iga): in the cut the firing cylinders sit at X=50-51
= -4.5..-4.9 deg BTDC (base ~37.5 deg from A272 load-col 0, minus 42). Target ~-20.

  A) IP_IGA_PUC_AT__N 2400/3500 cells 0xA19A/B : 0x10 -> 0x00  (-42 -> -48 deg relative)
  B) A272 main ignition, load column 0 (lowest, below idle load), rpm rows 3200..6000:
     -> 138 (28.1 deg BTDC), was 37-42 deg.   final ~= 28 - 48 = -20 deg BTDC
  C) C_IGA_LGRD_1 @0x83FA (u16 LE) 546 -> 2184: retard ramps in ~4x faster on a lift

  .venv\Scripts\python.exe roms\tunes\paddock-pops-tpsceil\build_loud.py
"""
import hashlib, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
POPS_DIR = os.path.join(os.path.dirname(HERE), 'paddock-pops')
src = open(os.path.join(POPS_DIR, 'build.py')).read()
ns = {'__file__': os.path.join(POPS_DIR, 'build.py')}
exec(src[:src.index('\nstock, burble, pucstage')], ns)   # reuse fix_checksums()

BASE = os.path.join(HERE, 'FULL_ca654019_paddock_pops_tpsceil160_nodhp_UNFLASHED.bin')
OUT = os.path.join(HERE, 'FULL_ca654019_paddock_pops_loud_UNFLASHED.bin')
base = open(BASE, 'rb').read()
img = bytearray(base)
assert img[0xA19A] == 0x10 and img[0xA19B] == 0x10
img[0xA19A] = img[0xA19B] = 0x00
rpm_axis = struct.unpack('<16H', base[0x8E94:0x8E94 + 32])
assert rpm_axis[9] == 3200 and rpm_axis[15] == 6000, rpm_axis
for r in range(9, 16):
    a = 0xA272 + r * 12
    assert 160 <= img[a] <= 180, (r, img[a])
    img[a] = 138
assert struct.unpack('<H', base[0x83FA:0x83FC])[0] == 546
img[0x83FA:0x83FC] = struct.pack('<H', 2184)
out = ns['fix_checksums'](bytes(img))
d = [i for i in range(len(out)) if out[i] != base[i]]
print('bytes changed vs nodhp image:', [hex(i) for i in d])
assert len(d) <= 2 + 7 + 2 + 2
print('full', hashlib.sha256(out).hexdigest()[:16], ' cal', hashlib.sha256(out[0x8000:0xDF40]).hexdigest()[:16])
open(OUT, 'wb').write(out)
print('written', OUT)
