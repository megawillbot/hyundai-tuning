r"""Paddock pops + raised TPS closed-learn ceiling (crutch for the +2 V TPS offset,
see docs/closed-throttle-recognition.md, 2026-09-19).

Base = the pops image that is on the car (verified by read-back 2026-09-18).
One cal byte: C_TPS_MAX_IS @ 0x8338, 64 -> 160, so the learned closed position
can reach the real closed reading (raw 135). Cal-only; program zone unchanged.

  .venv\Scripts\python.exe roms\tunes\paddock-pops-tpsceil\build.py
"""
import hashlib, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
POPS_DIR = os.path.join(os.path.dirname(HERE), 'paddock-pops')
src = open(os.path.join(POPS_DIR, 'build.py')).read()
# reuse fix_checksums() from the pops build without re-running that build
ns = {'__file__': os.path.join(POPS_DIR, 'build.py')}
exec(src[:src.index('\nstock, burble, pucstage')], ns)

BASE = os.path.join(POPS_DIR, 'FULL_ca654019_burblev2_paddock_pops_UNFLASHED.bin')
OUT = os.path.join(HERE, 'FULL_ca654019_paddock_pops_tpsceil160_UNFLASHED.bin')
base = open(BASE, 'rb').read()
img = bytearray(base)
assert img[0x8338] == 0x40 and img[0x8339] == 0xF9 and img[0x8335] == 0x03
img[0x8338] = 0xA0                     # C_TPS_MAX_IS 64 -> 160
out = ns['fix_checksums'](bytes(img))
d = [i for i in range(len(out)) if out[i] != base[i]]
print('bytes changed vs pops image:', [hex(i) for i in d])
assert set(d) <= {0x8338, 0xDEE0, 0xDEE1} and 0x8338 in d
print('full', hashlib.sha256(out).hexdigest()[:16], ' cal', hashlib.sha256(out[0x8000:0xDF40]).hexdigest()[:16])
open(OUT, 'wb').write(out)
print('written', OUT)
