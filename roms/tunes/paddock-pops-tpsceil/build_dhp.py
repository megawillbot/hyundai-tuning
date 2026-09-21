r"""Paddock pops + TPS ceiling 160 + dashpot wait removed (see notes.md, 2026-09-19).

Base = the tpsceil160 image that is on the car (verified by read-back).
One more cal byte: C_N_MIN_DHP @ 0x8238, 22 -> 255, so the state-4 -> overrun-cut
transition at 0x1C42A no longer waits for M_FD64.0 (dashpot decay). Cal-only.

  .venv\Scripts\python.exe roms\tunes\paddock-pops-tpsceil\build_dhp.py
"""
import hashlib, os
HERE = os.path.dirname(os.path.abspath(__file__))
POPS_DIR = os.path.join(os.path.dirname(HERE), 'paddock-pops')
src = open(os.path.join(POPS_DIR, 'build.py')).read()
# reuse fix_checksums() from the pops build without re-running that build
ns = {'__file__': os.path.join(POPS_DIR, 'build.py')}
exec(src[:src.index('\nstock, burble, pucstage')], ns)

BASE = os.path.join(HERE, 'FULL_ca654019_paddock_pops_tpsceil160_UNFLASHED.bin')
OUT = os.path.join(HERE, 'FULL_ca654019_paddock_pops_tpsceil160_nodhp_UNFLASHED.bin')
base = open(BASE, 'rb').read()
img = bytearray(base)
assert img[0x8238] == 0x16 and img[0x8338] == 0xA0
img[0x8238] = 0xFF                     # C_N_MIN_DHP 22 -> 255
out = ns['fix_checksums'](bytes(img))
d = [i for i in range(len(out)) if out[i] != base[i]]
print('bytes changed vs tpsceil160 image:', [hex(i) for i in d])
assert set(d) <= {0x8238, 0xDEE0, 0xDEE1} and 0x8238 in d
print('full', hashlib.sha256(out).hexdigest()[:16], ' cal', hashlib.sha256(out[0x8000:0xDF40]).hexdigest()[:16])
open(OUT, 'wb').write(out)
print('written', OUT)
