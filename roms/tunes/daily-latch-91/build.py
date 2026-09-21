r"""Daily tune: stock overrun behaviour + NZ 91 timing, with the whole event setup behind the latch.

See notes.md in this folder. Two zones change (flash cal FIRST, then program):

  program : paddock-pops program (89 B vs stock, on the car since 2026-09-18) + 11 "latch
            switch" stubs. Each replaces one 4-byte table-pointer / constant load with a
            CALLS to a 14-byte stub that does the stock load and, only while the latch
            M_FD40.15 is set, overrides it with an alternate copy in free cal space.
  cal     : ghost-cam cal (= stock overrun: staged full cut, resume 1248-1600, stock PU/PUC
            ignition, stock dashpot) + 91 RON cut on the base ignition map + the alternate
            ("armed") tables = the 2026-09-20 event cal (`paddock_pops_instant`) + arm 6016 /
            disarm 896 rpm.

Unarmed the car never reads an alternate table. Stub A's arm threshold moves to a new cal
byte 0xBC93 (FF in every older cal), so on any cal without the alternates the latch never
arms and the program is inert by construction. 0xBC91 is kept at the same value for the
old program (cal-first flash order).

  .venv\Scripts\python.exe roms\tunes\daily-latch-91\build.py
"""
import hashlib, os, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
POPS_DIR = os.path.join(os.path.dirname(HERE), 'paddock-pops')
src = open(os.path.join(POPS_DIR, 'build.py')).read()
ns = {'__file__': os.path.join(POPS_DIR, 'build.py')}
exec(src[:src.index('\nstock, burble, pucstage')], ns)   # reuse fix_checksums()

EVENT = os.path.join(os.path.dirname(HERE), 'paddock-pops-tpsceil', 'FULL_ca654019_paddock_pops_instant_UNFLASHED.bin')
GHOST = os.path.join(os.path.dirname(HERE), 'ghostcam_ca654019_2026-08-31.bin')
STOCK = os.path.join(ROOT, 'roms', 'stock', 'FULL_ca654019_stock_merged.bin')
OUT = os.path.join(HERE, 'FULL_ca654019_daily_latch_91_UNFLASHED.bin')
CAL = (0x8000, 0xDF40)
PROG = (0x10000, 0x4A6A6)

event, ghost, stock = (open(p, 'rb').read() for p in (EVENT, GHOST, STOCK))
img = bytearray(event)

# ------------------------------------------------------------------ calibration
img[CAL[0]:CAL[1]] = ghost[CAL[0]:CAL[1]]
assert img[0xBC8B:0xC000] == b'\xFF' * (0xC000 - 0xBC8B), 'free cal space is not free'

# latch + final-stage pattern (the existing patch)
img[0xBC8B:0xBC91] = bytes([0x0D, 0x0D, 0x0D, 0x0D, 6, 6])   # PUC_3 on axis 704/992/1312/1600/2016/2496: pattern 6 from 2016 rpm
img[0xBC91] = 188                                            # C_N_ARM_POP    = 6016 rpm
img[0xBC92] = 28                                             # C_N_DISARM_POP =  896 rpm
img[0xBC93] = 188                                            # C_N_ARM_POP_2: the arm byte THIS program reads (see stub A below)

# 91 RON: retard on the base map IP_IGAB__N__MAF (0xA272, 16 rpm x 12 load, 0.375 deg/count).
# Counts to remove per (rpm row, load col); measured knock retard + ~1 deg, see notes.md.
RPM = struct.unpack('<16H', ghost[0x8E94:0x8E94 + 32])
assert RPM == (420, 700, 1000, 1200, 1500, 1800, 2200, 2600, 3000, 3200, 3700, 4000, 4500, 5050, 5550, 6000)
#            col: 5   6   7   8   9  10  11      (cols 0-4, load < ~230 mg/stroke, untouched)
CUT91 = {1500: (0,  4,  4,  4,  4,  4,  4),
         1800: (4,  8,  8,  8,  8,  8,  8),
         2200: (6, 12, 12, 12, 12, 12, 12),
         2600: (6, 12, 12, 12, 12, 12, 12),
         3000: (4, 10, 10, 10, 10, 10, 10),
         3200: (4, 10, 10, 10, 10, 10, 10),
         3700: (0,  4,  8,  8,  8,  8,  8),
         4000: (0,  4,  8,  8,  8,  8,  8),
         4500: (0,  4,  8,  8,  8,  8,  8),
         5050: (0,  2,  6,  6,  6,  6,  6),
         5550: (0,  0,  4,  4,  4,  4,  4),
         6000: (0,  0,  4,  4,  4,  4,  4)}
for rpm, cuts in CUT91.items():
    r = RPM.index(rpm)
    for c, n in zip(range(5, 12), cuts):
        a = 0xA272 + r * 12 + c
        assert img[a] == stock[a] and img[a] - n >= 60, (rpm, c, img[a])
        img[a] -= n

# alternate ("armed") tables = the event cal, in free cal below 0xC000 (DPP0 window, like PUC_3)
ALT_LGRD, ALT_DHPMIN, ALT_PUC, ALT_PU, ALT_RESUME, ALT_DHP, ALT_IGAB = 0xBC94, 0xBC96, 0xBC98, 0xBC9C, 0xBCAC, 0xBCD6, 0xBCFA
assert ALT_LGRD % 2 == 0                                     # word access
img[ALT_LGRD:ALT_LGRD + 2] = event[0x83FA:0x83FC]            # C_IGA_LGRD_1 2184
img[ALT_DHPMIN] = event[0x8238]                              # C_N_MIN_DHP 255 (no dashpot wait)
img[ALT_PUC:ALT_PUC + 4] = event[0xA198:0xA19C]              # IP_IGA_PUC_AT__N 75/0/0/0
img[ALT_PU:ALT_PU + 16] = event[0xA184:0xA194]               # IP_IGA_PU_AT__N__TCO burble v2 rows
assert event[0xA91F:0xA91F + 42] == event[0xA8C4:0xA8C4 + 42] == b'\x3F' * 42
img[ALT_RESUME:ALT_RESUME + 42] = event[0xA91F:0xA91F + 42]  # both resume tables: 2016 rpm
img[ALT_DHP:ALT_DHP + 35] = event[0xA3AD:0xA3AD + 35]        # IP_ISAPWM_DHP_AT hold-open
igab = bytearray(img[0xA272:0xA272 + 192])                   # 91 map ...
for r in range(6, 16):
    for c in (0, 1):
        assert event[0xA272 + r * 12 + c] == 138
        igab[r * 12 + c] = 138                               # ... + the event's 28 deg overrun columns
img[ALT_IGAB:ALT_IGAB + 192] = igab
assert ALT_IGAB + 192 <= 0xC000
assert struct.unpack('<H', img[ALT_LGRD:ALT_LGRD + 2])[0] == 2184 and img[ALT_DHPMIN] == 255

# ------------------------------------------------------------------ program
LATCH_JNB = bytes([0x9A, 0x20, 0x02, 0xF0])                  # JNB M_FD40.15, +2 words (over the 4-byte override)
RETS = bytes([0xDB, 0x00])


def dpp0(cal_addr):
    assert 0x8000 <= cal_addr < 0xC000
    return struct.pack('<H', cal_addr - 0x8000)


def ptr_stub(stock_cal, alt_cal):                            # MOV R12,#stock ; JNB latch ; MOV R12,#alt ; RETS
    return bytes([0xE6, 0xFC]) + dpp0(stock_cal) + LATCH_JNB + bytes([0xE6, 0xFC]) + dpp0(alt_cal) + RETS


def mem_stub(op, stock_cal, alt_cal):                        # <op> [stock] ; JNB latch ; <op> [alt] ; RETS
    return op + dpp0(stock_cal) + LATCH_JNB + op + dpp0(alt_cal) + RETS


# (site(s), stock 4 bytes at the site, stub)
SITES = [
    ([0x144FC], ptr_stub(0x99D0, 0xBC8B)),                   # ID_PAT_INH_IV_PUC_1 -> PUC_3 (cut from the first cycle)
    ([0x1453E], ptr_stub(0x99D6, 0xBC8B)),                   # ID_PAT_INH_IV_PUC_2 -> PUC_3
    ([0x20FD6], ptr_stub(0xA198, ALT_PUC)),                  # IP_IGA_PUC_AT__N
    ([0x2101A], ptr_stub(0xA184, ALT_PU)),                   # IP_IGA_PU_AT__N__TCO
    ([0x1C874], ptr_stub(0xA91F, ALT_RESUME)),               # IP_N_MIN_PUC_AT
    ([0x1C8AA], ptr_stub(0xA8C4, ALT_RESUME)),               # IP_N_ACCIN_MIN_PUC_AT
    ([0x221C6], ptr_stub(0xA3AD, ALT_DHP)),                  # IP_ISAPWM_DHP_AT__N__TPS
    ([0x20E3E], ptr_stub(0xA272, ALT_IGAB)),                 # IP_IGAB__N__MAF
    ([0x1C42E, 0x1C434], mem_stub(bytes([0x43, 0xFA]), 0x8238, ALT_DHPMIN)),   # CMPB RL5,[C_N_MIN_DHP]
    ([0x21102], mem_stub(bytes([0xF2, 0xFD]), 0x83FA, ALT_LGRD)),              # MOV R13,[C_IGA_LGRD_1]
    ([0x212AC], mem_stub(bytes([0xF2, 0xF9]), 0x83FA, ALT_LGRD)),              # MOV R9,[C_IGA_LGRD_1]
]
# Stub A reads its arm threshold from 0xBC93 instead of 0xBC91. 0xBC93 is FF in every older cal
# (incl. all event cals, which arm at 3200 rpm via 0xBC91 but have FF where the alternates live),
# so this program can never arm on a cal that lacks the alternate tables. Found in review 2026-09-21.
assert img[0x1104C:0x11050] == bytes([0x43, 0xF8, 0x91, 0x3C])   # CMPB RL4,[0x3C91]
img[0x1104E] = 0x93
at = 0x11060
assert img[at:0x11F02] == b'\xFF' * (0x11F02 - at)
stub_bytes = 0
for sites, stub in SITES:
    assert len(stub) == 14
    img[at:at + 14] = stub
    for s in sites:
        assert img[s:s + 4] == stub[:4] == stock[s:s + 4], hex(s)   # the site holds exactly the instruction the stub re-does
        img[s:s + 4] = bytes([0xDA, 0x09]) + struct.pack('<H', at - 0x10000)   # CALLS 0x09,<stub>
    at += 16
    stub_bytes += 14

out = ns['fix_checksums'](bytes(img))

# ------------------------------------------------------------------ accounting
assert out[:CAL[0]] == event[:CAL[0]] and out[CAL[1]:PROG[0]] == event[CAL[1]:PROG[0]] and out[PROG[1]:] == event[PROG[1]:]
pd = [i for i in range(*PROG) if out[i] != event[i]]
site_bytes = sum(1 for sites, _ in SITES for s in sites for k in range(4) if out[s + k] != event[s + k])
print(f'program vs the program on the car: {len(pd)} bytes = {stub_bytes} stub + {site_bytes} site + 1 (stub A arm address) + checksum')
assert set(pd) - set(range(0x10010, 0x10012)) - {0x1104E} == \
    {i for i in range(0x11060, at) if out[i] != 0xFF} | {s + k for sites, _ in SITES for s in sites for k in range(4) if out[s + k] != event[s + k]}
assert out[0x1004E:0x10080] == stock[0x1004E:0x10080]        # coherence block untouched
cd = [i for i in range(*CAL) if out[i] != ghost[i]]
n91 = sum(1 for v in CUT91.values() for n in v if n)
print(f'cal vs ghost-cam cal: {len(cd)} bytes ({n91} base-map cells, 8 latch bytes, {0xBC94 and (ALT_IGAB + 192 - ALT_LGRD)} alt-table span, checksum)')
assert all(0xA272 <= i < 0xA272 + 192 or 0xBC8B <= i < ALT_IGAB + 192 or i in (0xDEE0, 0xDEE1) for i in cd)

# disassemble the stubs and sites from the built image and print them for review
dis = os.path.join(ROOT, 'tools', 'c166', 'c166dis.py')
tmp = OUT + '.tmp'
open(tmp, 'wb').write(out)
lst = subprocess.run([sys.executable, dis, tmp, '10000', '4A6A6'], capture_output=True, text=True, env=dict(os.environ, PYTHONUTF8='1')).stdout.splitlines()
os.remove(tmp)
want = {s for sites, _ in SITES for s in sites}
for ln in lst:
    a = int(ln[:5], 16) if ln[:5].strip() and all(ch in '0123456789ABCDEFabcdef' for ch in ln[:5]) else -1
    if 0x11040 <= a < 0x1105A or 0x11060 <= a < at or a in want:
        print('  ' + ln.rstrip())

print('full', hashlib.sha256(out).hexdigest()[:16], ' cal', hashlib.sha256(out[CAL[0]:CAL[1]]).hexdigest()[:16],
      ' program', hashlib.sha256(out[PROG[0]:PROG[1]]).hexdigest()[:16])
open(OUT, 'wb').write(out)
print('written', OUT)
