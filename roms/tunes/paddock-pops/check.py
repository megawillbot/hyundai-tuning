r"""Compare an ECU read-back against a candidate image, zone by zone.

  .venv\Scripts\python.exe roms\tunes\paddock-pops\check.py <readback.bin> <candidate.bin> [cal|program]

With no zone argument both zones are compared. A calibration read-back is
compared over file 0x8000-0xDF40; a program read-back over 0x10000-0x4A6A6
(the code region; everything past it is erased flash).
"""
import hashlib, sys

ZONES = {'cal': (0x8000, 0xDF40), 'program': (0x10000, 0x4A6A6)}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    a = open(sys.argv[1], 'rb').read()
    b = open(sys.argv[2], 'rb').read()
    which = sys.argv[3:] or list(ZONES)
    ok = True
    for z in which:
        lo, hi = ZONES[z]
        da, db = a[lo:hi], b[lo:hi]
        bad = [i for i in range(len(da)) if da[i] != db[i]]
        print(f'{z:8s} readback {hashlib.sha256(da).hexdigest()[:16]}  candidate {hashlib.sha256(db).hexdigest()[:16]}  '
              + ('MATCH' if not bad else f'{len(bad)} BYTES DIFFER, first at {lo + bad[0]:#x}'))
        ok &= not bad
    print('OK' if ok else 'MISMATCH - re-flash this zone before starting the engine')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
