r"""Paddock pops 'instant': wide image + the two cut-entry stages also use pattern 6.

Stock entry: 11 cycles of PUC_1 (index 4 = one injector) then 11 cycles of PUC_2
(index 9 = four injectors) before the final stage. At ~2300 rpm that is ~1.1 s, which
is most of a D-range lift (2026-09-19 21:41 test drive). ID_PAT_INH_IV_PUC_1 @0x99D0
and _PUC_2 @0x99D6 (6 cells each, axis 0x8757): all -> 6, so the three-cylinder
pattern runs from the first cycle of every cut. The entry stages are not behind the
arm latch: an unarmed lift gets 22 cycles of pattern 6, then the stock all-six cut.

  .venv\Scripts\python.exe roms\tunes\paddock-pops-tpsceil\build_instant.py
"""
import hashlib, os
HERE = os.path.dirname(os.path.abspath(__file__))
POPS_DIR = os.path.join(os.path.dirname(HERE), 'paddock-pops')
src = open(os.path.join(POPS_DIR, 'build.py')).read()
ns = {'__file__': os.path.join(POPS_DIR, 'build.py')}
exec(src[:src.index('\nstock, burble, pucstage')], ns)   # reuse fix_checksums()

BASE = os.path.join(HERE, 'FULL_ca654019_paddock_pops_wide_UNFLASHED.bin')
OUT = os.path.join(HERE, 'FULL_ca654019_paddock_pops_instant_UNFLASHED.bin')
base = open(BASE, 'rb').read()
img = bytearray(base)
assert base[0x99D0:0x99DC] == b'\x04' * 6 + b'\x09' * 6
img[0x99D0:0x99DC] = b'\x06' * 12
out = ns['fix_checksums'](bytes(img))
d = [i for i in range(len(out)) if out[i] != base[i]]
print('bytes changed vs wide image:', [hex(i) for i in d])
assert set(d) <= set(range(0x99D0, 0x99DC)) | {0xDEE0, 0xDEE1}
print('full', hashlib.sha256(out).hexdigest()[:16], ' cal', hashlib.sha256(out[0x8000:0xDF40]).hexdigest()[:16])
open(OUT, 'wb').write(out)
print('written', OUT)
