r"""Paddock pops 'loud + air', v2: loud_air image + A272 load column 1 lowered too.

With the IACV restrictor plate out (2026-09-19 14:08) the cut runs on more air
(pulse 385-590 vs 290-350) and the base angle interpolates toward A272 column 1,
costing 2-5 deg of retard. Column 1, rpm rows 3200..6000 -> 138 (28.1 deg), same
as column 0, so the cut stays ~-20 deg BTDC with the idle valve held open.

  .venv\Scripts\python.exe roms\tunes\paddock-pops-tpsceil\build_loud_air2.py
"""
import hashlib, os
HERE = os.path.dirname(os.path.abspath(__file__))
POPS_DIR = os.path.join(os.path.dirname(HERE), 'paddock-pops')
src = open(os.path.join(POPS_DIR, 'build.py')).read()
ns = {'__file__': os.path.join(POPS_DIR, 'build.py')}
exec(src[:src.index('\nstock, burble, pucstage')], ns)   # reuse fix_checksums()

BASE = os.path.join(HERE, 'FULL_ca654019_paddock_pops_loud_air_UNFLASHED.bin')
OUT = os.path.join(HERE, 'FULL_ca654019_paddock_pops_loud_air2_UNFLASHED.bin')
base = open(BASE, 'rb').read()
img = bytearray(base)
for r in range(9, 16):
    a = 0xA272 + r * 12
    assert img[a] == 138 and 155 <= img[a + 1] <= 180, (r, img[a], img[a + 1])
    img[a + 1] = 138
out = ns['fix_checksums'](bytes(img))
d = [i for i in range(len(out)) if out[i] != base[i]]
print('bytes changed vs loud_air image:', [hex(i) for i in d])
assert len(d) <= 9
print('full', hashlib.sha256(out).hexdigest()[:16], ' cal', hashlib.sha256(out[0x8000:0xDF40]).hexdigest()[:16])
open(OUT, 'wb').write(out)
print('written', OUT)
