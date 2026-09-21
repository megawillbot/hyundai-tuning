r"""Paddock pops 'wide': pop window 3008 -> 2016 rpm, on top of loud_air2 + stock TPS ceiling.

Base = build_final.py output (loud_air2 with C_TPS_MAX_IS back at 64).

  1) Cut resume IP_N_MIN_PUC_AT (0xA91F, 42 B) and the ACCIN variant (0xA8C4, 42 B):
     94 -> 63 = 2016 rpm. Cut engages at resume + 192 rpm (2208), or + 512 after a recent cut.
  2) PUC_3 pattern table (axis 0x8757 = 704/992/1312/1600/2016/3008): 5th cell 0xBC8F
     0x0D -> 6, so pattern 6 covers everything from 2016 rpm up (top two cells both 6, so
     the result is the same whether the ID lookup steps or interpolates).
  3) IP_IGA_PUC_AT__N 1600 cell 0xA199: 61 -> 0, so the cut holds -48 deg relative down
     to 2016 rpm instead of fading toward -25.
  4) A272 base map, load columns 0 and 1, rpm rows 2200/2600/3000 -> 138 (28.1 deg), same
     as the 3200+ rows: keeps the cut at ~-20 deg BTDC across the wider window. Row 1800
     is left stock (final ~-16 deg at 2016 rpm by interpolation).
  5) Dashpot hold-open IP_ISAPWM_DHP_AT row 2240 rpm, closed-throttle column: 0 -> 0x40
     (tapers to 0 at 1696 rpm) so there is still air at the bottom of the window.

Why 2016 and not lower: the auto coasts at 1340-1450 rpm in D, and the latch stays armed
until rpm dips below 1024, so a lower resume would run a three-cylinder cut during
ordinary coasting. Unarmed lifts get the stock all-six cut between 2208 and 2016 rpm.

  .venv\Scripts\python.exe roms\tunes\paddock-pops-tpsceil\build_wide.py
"""
import hashlib, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
POPS_DIR = os.path.join(os.path.dirname(HERE), 'paddock-pops')
src = open(os.path.join(POPS_DIR, 'build.py')).read()
ns = {'__file__': os.path.join(POPS_DIR, 'build.py')}
exec(src[:src.index('\nstock, burble, pucstage')], ns)   # reuse fix_checksums()

BASE = os.path.join(HERE, 'FULL_ca654019_paddock_pops_loud_air2_stockceil_UNFLASHED.bin')
OUT = os.path.join(HERE, 'FULL_ca654019_paddock_pops_wide_UNFLASHED.bin')
base = open(BASE, 'rb').read()
img = bytearray(base)
assert img[0x8338] == 0x40
assert list(base[0x8756:0x875D]) == [6, 0x16, 0x1F, 0x29, 0x32, 0x3F, 0x5E]
for a in (0xA91F, 0xA8C4):
    assert base[a:a + 42] == b'\x5E' * 42
    img[a:a + 42] = b'\x3F' * 42
assert list(base[0xBC8B:0xBC93]) == [0x0D] * 5 + [6, 0x64, 0x20]
img[0xBC8F] = 0x06
assert list(base[0xA198:0xA19C]) == [75, 61, 0, 0]
img[0xA199] = 0x00
rpm_axis = struct.unpack('<16H', base[0x8E94:0x8E94 + 32])
assert rpm_axis[6:9] == (2200, 2600, 3000), rpm_axis
for r in (6, 7, 8):
    for c in (0, 1):
        a = 0xA272 + r * 12 + c
        assert 155 <= img[a] <= 180, (r, c, img[a])
        img[a] = 138
assert list(base[0xA3AD + 20:0xA3AD + 25]) == [0, 0x0F, 0x0F, 0x48, 0x48]
img[0xA3AD + 20] = 0x40
out = ns['fix_checksums'](bytes(img))
d = [i for i in range(len(out)) if out[i] != base[i]]
print('bytes changed vs stockceil image: %d' % len(d), [hex(i) for i in d if not (0xA8C4 <= i < 0xA8C4 + 42 or 0xA91F <= i < 0xA91F + 42)])
assert len(d) == 84 + 1 + 1 + 6 + 1 + 2
print('full', hashlib.sha256(out).hexdigest()[:16], ' cal', hashlib.sha256(out[0x8000:0xDF40]).hexdigest()[:16])
open(OUT, 'wb').write(out)
print('written', OUT)
