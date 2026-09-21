r"""Paddock pops 'loud + air': loud image + idle valve held open during the cut.

IP_ISAPWM_DHP_AT__N__TPS @0xA3AD (7 rpm x 5 TPS, rpm-major; rpm axis 608/896/992/
1696/2240/3488/5504, TPS axis 2/3/10/21/43). Column 0 (closed throttle) is 0 at
every rpm, so the dashpot decays to nothing and the cut runs on leak air only.
Rows 3488 and 5504, column 0: 0 -> 0x80. Interpolates to 0 at 2240 rpm, so idle
and low-rpm decel are untouched. (M_FD0C.7 = AT table confirmed set in RAM.)

  .venv\Scripts\python.exe roms\tunes\paddock-pops-tpsceil\build_loud_air.py
"""
import hashlib, os
HERE = os.path.dirname(os.path.abspath(__file__))
POPS_DIR = os.path.join(os.path.dirname(HERE), 'paddock-pops')
src = open(os.path.join(POPS_DIR, 'build.py')).read()
ns = {'__file__': os.path.join(POPS_DIR, 'build.py')}
exec(src[:src.index('\nstock, burble, pucstage')], ns)   # reuse fix_checksums()

BASE = os.path.join(HERE, 'FULL_ca654019_paddock_pops_loud_UNFLASHED.bin')
OUT = os.path.join(HERE, 'FULL_ca654019_paddock_pops_loud_air_UNFLASHED.bin')
base = open(BASE, 'rb').read()
img = bytearray(base)
assert list(base[0x8A7D:0x8A85]) == [7, 0x13, 0x1C, 0x1F, 0x35, 0x46, 0x6D, 0xAC]
assert list(base[0xA3AD + 25:0xA3AD + 35]) == [0, 0x33, 0x33, 0x4D, 0x80, 0, 0x33, 0x33, 0x5A, 0xA6]
img[0xA3AD + 25] = 0x80    # 3488 rpm, TPS col 0
img[0xA3AD + 30] = 0x80    # 5504 rpm, TPS col 0
out = ns['fix_checksums'](bytes(img))
d = [i for i in range(len(out)) if out[i] != base[i]]
print('bytes changed vs loud image:', [hex(i) for i in d])
assert set(d) <= {0xA3AD + 25, 0xA3AD + 30, 0xDEE0, 0xDEE1}
print('full', hashlib.sha256(out).hexdigest()[:16], ' cal', hashlib.sha256(out[0x8000:0xDF40]).hexdigest()[:16])
open(OUT, 'wb').write(out)
print('written', OUT)
