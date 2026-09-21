r"""Live check of the raw logger CSVs for the paddock pops tune.

  .venv\Scripts\python.exe roms\tunes\paddock-pops\livecheck.py [--all]

Reads every log_raw_2026-09-18_19*.csv in tools/GKFlasher (the test-drive
session), decodes the channels that matter (positions from
docs/logger-remap-ca654019.md) and prints:
  - session summary (frames, coolant range, max rpm)
  - every "lift" event: TPS <= 45 with rpm > 2800, grouped into runs, with the
    per-cylinder injection values and the ignition byte along the way
  - the last 10 frames, so a mid-drive check shows what is happening now
"""
import glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import time
# select only log files touched in the last 15 min (the current run), so old drives don't mix in
_all = glob.glob(os.path.join(ROOT, 'tools', 'GKFlasher', 'log_raw_*.csv'))
FILES = sorted(f for f in _all if time.time() - os.path.getmtime(f) < 900)


def frames():
    for f in FILES:
        with open(f) as fh:
            for line in fh:
                parts = line.strip().split(',', 1)
                if len(parts) != 2:
                    continue
                try:
                    ts = int(parts[0]); b = [int(x, 16) for x in parts[1].split()]
                except ValueError:
                    continue
                if len(b) < 60:
                    continue
                yield os.path.basename(f), ts, b


def decode(b):
    rpm = b[20] | (b[21] << 8)
    inj = [b[43 + 2 * i] | (b[44 + 2 * i] << 8) for i in range(6)]
    return dict(rpm=rpm, tps=b[11], cool=round(0.75 * b[4] - 48), ign=b[37], inj=inj,
                cut=sum(1 for v in inj if v < 100), state28=b[28], speed=b[19])


rows = [(f, ts, decode(b)) for f, ts, b in frames()]
if not rows:
    print('no frames yet'); sys.exit(0)
t0 = rows[0][1]
print(f'files: {sorted(set(r[0] for r in rows))}')
print(f'frames: {len(rows)}  span: {(rows[-1][1]-t0)/1000:.0f} s  coolant {min(r[2]["cool"] for r in rows)}..{max(r[2]["cool"] for r in rows)} C  max rpm {max(r[2]["rpm"] for r in rows)}')

# lift runs: consecutive frames with tps<=45 and rpm>2800
runs, cur = [], []
for f, ts, d in rows:
    if d['tps'] <= 45 and d['rpm'] > 2800:
        cur.append((ts, d))
    elif cur:
        runs.append(cur); cur = []
if cur:
    runs.append(cur)
print(f'\nlift events above 2800 rpm with foot off: {len(runs)}')
for i, run in enumerate(runs, 1):
    print(f'-- lift {i}: t={(run[0][0]-t0)/1000:.1f}s, {len(run)} frames, rpm {run[0][1]["rpm"]} -> {run[-1][1]["rpm"]}, '
          f'max cut cylinders {max(d["cut"] for _, d in run)}')
    for ts, d in run[:14]:
        print(f'   t={(ts-t0)/1000:7.1f}  rpm {d["rpm"]:4d}  tps {d["tps"]:3d}  ign {d["ign"]:3d}  cut {d["cut"]}  inj {d["inj"]}')
    if len(run) > 14:
        print(f'   ... {len(run)-14} more frames')

if '--all' not in sys.argv:
    print('\nlast 10 frames:')
    for f, ts, d in rows[-10:]:
        print(f'   t={(ts-t0)/1000:7.1f}  rpm {d["rpm"]:4d}  tps {d["tps"]:3d}  cool {d["cool"]:3d}  ign {d["ign"]:3d}  cut {d["cut"]}  inj {d["inj"]}  b28 {d["state28"]}')
