r"""Paddock pops 'loud + air2' with the TPS learn ceiling back at stock.

After the TPS was re-seated (2026-09-19 21:19: closed raw 13, full open 214, no
rail, no fault) the 0x8338 crutch is no longer needed: C_TPS_MAX_IS 160 -> 64.
Everything else (nodhp, loud ignition, dashpot hold-open) is kept.

  .venv\Scripts\python.exe roms\tunes\paddock-pops-tpsceil\build_final.py
"""
import hashlib, os
HERE = os.path.dirname(os.path.abspath(__file__))
POPS_DIR = os.path.join(os.path.dirname(HERE), 'paddock-pops')
src = open(os.path.join(POPS_DIR, 'build.py')).read()
ns = {'__file__': os.path.join(POPS_DIR, 'build.py')}
exec(src[:src.index('\nstock, burble, pucstage')], ns)   # reuse fix_checksums()

BASE = os.path.join(HERE, 'FULL_ca654019_paddock_pops_loud_air2_UNFLASHED.bin')
OUT = os.path.join(HERE, 'FULL_ca654019_paddock_pops_loud_air2_stockceil_UNFLASHED.bin')
base = open(BASE, 'rb').read()
img = bytearray(base)
assert img[0x8338] == 0xA0
img[0x8338] = 0x40
out = ns['fix_checksums'](bytes(img))
d = [i for i in range(len(out)) if out[i] != base[i]]
print('bytes changed vs loud_air2 image:', [hex(i) for i in d])
assert set(d) <= {0x8338, 0xDEE0, 0xDEE1}
print('full', hashlib.sha256(out).hexdigest()[:16], ' cal', hashlib.sha256(out[0x8000:0xDF40]).hexdigest()[:16])
open(OUT, 'wb').write(out)
print('written', OUT)
