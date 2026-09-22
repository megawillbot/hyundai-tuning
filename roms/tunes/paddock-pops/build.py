# SPDX-License-Identifier: GPL-3.0-or-later
# Imports GKFlasher (GPL-3.0) modules, so this file is GPL-3.0-or-later; see LICENSE.
r"""Build the paddock pops & bangs images (see notes.md in this folder).

Both images share the reviewed program zone of
roms/tunes/puc-final-stage-patch/ (89 bytes differ from stock) and carry the
running burble v2 calibration forward.

  rehearsal : patched program + burble v2 cal + the new cal bytes at INERT
              values. Behaviourally identical to the car today.
  pops      : same program; cal-only changes on top of the rehearsal.

Run from the repo root with the project venv:
  .venv\Scripts\python.exe roms\tunes\paddock-pops\build.py
"""
import hashlib, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'GKFlasher'))
from flasher.checksum import detect_offsets, checksum, read_and_reverse, concat_3_bytes  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
STOCK = os.path.join(ROOT, 'roms/stock/FULL_ca654019_stock_merged.bin')
BURBLE_V2 = os.path.join(ROOT, 'roms/tunes/burble/cal_ca654019_ghostcam_burble_v2_UNFLASHED.bin')
PUCSTAGE = os.path.join(ROOT, 'roms/tunes/puc-final-stage-patch/FULL_ca654019_ghostcam_pucstage_UNFLASHED.bin')
OUT_REHEARSAL = os.path.join(HERE, 'FULL_ca654019_burblev2_pucstage_rehearsal_UNFLASHED.bin')
OUT_POPS = os.path.join(HERE, 'FULL_ca654019_burblev2_paddock_pops_UNFLASHED.bin')

CAL = (0x8000, 0xDF40)      # calibration zone in the file
PROG = (0x10000, 0x80000)   # program zone in the file


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fix_checksums(img):
    """Same arithmetic as GKFlasher's correct_checksum(), applied in memory."""
    img = bytearray(img)
    t = detect_offsets(bytes(img))
    assert t and t['name'] == 'v6 (5WY17)', t
    for region in t['regions']:
        cks_address, init_address, bin_offset = region['cks_address'], region['init_address'], region['bin_offset']
        zones = img[cks_address + 2]
        if zones in (0, 0xFF):
            continue
        cks = []
        za = cks_address
        for i in range(zones):
            start = concat_3_bytes(read_and_reverse(img, za + 4, 3)) + bin_offset
            stop = concat_3_bytes(read_and_reverse(img, za + 8, 3)) + bin_offset + 1
            if i == 0:
                ib = read_and_reverse(img, init_address, 2)
                init = (ib[0] << 8) | ib[1]
            else:
                init = cks[-1]
            cks.append(checksum(bytes(img), start, stop, init))
            za += 8
        rev = ((cks[-1] & 0xFF) << 8) | ((cks[-1] >> 8) & 0xFF)
        img[cks_address:cks_address + 2] = rev.to_bytes(2, 'big')
        print(f'  {region["name"]:12s} checksum -> {rev:#06x}')
    return bytes(img)


def diff(a, b, lo, hi):
    return [i for i in range(lo, hi) if a[i] != b[i]]


stock, burble, pucstage = rd(STOCK), rd(BURBLE_V2), rd(PUCSTAGE)
assert len(stock) == len(burble) == len(pucstage) == 0x80000

# ---- rehearsal: pucstage image with its cal zone replaced by burble v2, plus inert new bytes
img = bytearray(pucstage)
img[CAL[0]:CAL[1]] = burble[CAL[0]:CAL[1]]
assert img[0xBC8B:0xBC93] == b'\xFF' * 8, 'new-table bytes are not free in the burble v2 cal'
img[0xBC8B:0xBC91] = b'\x0D' * 6   # ID_PAT_INH_IV_PUC_3__N_32: all six = stock final stage
img[0xBC91] = 0xFF                 # C_N_ARM_POP    = 8160 rpm, never arms
img[0xBC92] = 0x20                 # C_N_DISARM_POP = 1024 rpm
print('rehearsal:')
rehearsal = fix_checksums(bytes(img))

# ---- pops: cal-only changes on top of the rehearsal
img = bytearray(rehearsal)
img[0xA91F:0xA91F + 42] = b'\x5E' * 42   # IP_N_MIN_PUC_AT__TCO__GR_MT       -> 94 = 3008 rpm resume, every cell
img[0xA8C4:0xA8C4 + 42] = b'\x5E' * 42   # IP_N_ACCIN_MIN_PUC_AT__TCO__GR_MT -> same, for the M_FD8C.14 variant
img[0x875C] = 0x5E                       # top breakpoint of the 0x8757 rpm/32 axis: 2496 -> 3008 rpm
img[0xA19A] = 0x10                       # IP_IGA_PUC_AT__N 2400 cell: -25.1 -> -42.0 deg relative
img[0xA19B] = 0x10                       # IP_IGA_PUC_AT__N 3500 cell: -25.1 -> -42.0 deg relative
img[0xBC90] = 0x06                       # PUC_3 top cell: pattern 6 = 101100, three injectors cut
img[0xBC91] = 0x64                       # C_N_ARM_POP = 100 -> 3200 rpm
print('pops:')
pops = fix_checksums(bytes(img))

# ---- accounting
assert rehearsal[PROG[0]:PROG[1]] == pucstage[PROG[0]:PROG[1]] == pops[PROG[0]:PROG[1]]
assert rehearsal[:CAL[0]] == pucstage[:CAL[0]] == pops[:CAL[0]]
assert rehearsal[CAL[1]:PROG[0]] == pucstage[CAL[1]:PROG[0]] == pops[CAL[1]:PROG[0]]
pd = diff(rehearsal, stock, *PROG)
rd_ = diff(rehearsal, burble, *CAL)
pp = diff(pops, rehearsal, *CAL)
print(f'program zone vs stock: {len(pd)} bytes differ (expect 89)')
print(f'rehearsal cal vs burble v2: {len(rd_)} bytes differ (expect 9): {[hex(i) for i in rd_]}')
print(f'pops cal vs rehearsal: {len(pp)} bytes differ (expect 91)')
assert len(pd) == 89 and len(rd_) == 9 and len(pp) == 91
assert set(pp) == set(range(0xA91F, 0xA91F + 42)) | set(range(0xA8C4, 0xA8C4 + 42)) | {0x875C, 0xA19A, 0xA19B, 0xBC90, 0xBC91, 0xDEE0, 0xDEE1}

for name, b in [('rehearsal', rehearsal), ('pops', pops)]:
    print(f'{name}: full {sha(b)[:16]}  cal {sha(b[CAL[0]:CAL[1]])[:16]}  program {sha(b[PROG[0]:PROG[1]])[:16]}')
with open(OUT_REHEARSAL, 'wb') as f:
    f.write(rehearsal)
with open(OUT_POPS, 'wb') as f:
    f.write(pops)
print('written', OUT_REHEARSAL, OUT_POPS)
