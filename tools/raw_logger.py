# SPDX-License-Identifier: GPL-3.0-or-later
# Imports GKFlasher (GPL-3.0) modules, so this file is GPL-3.0-or-later; see LICENSE.
"""Drive-safe RAW datalogger.
Reuses GKFlasher's exact connect/security/identify, but runs logger_raw instead
of logger -- capturing the full untranslated ReadDataByLocalIdentifier(0x01)
block as hex, flushed every 10 frames. Drop-safe (a kill loses <=10 frames), and
the raw bytes let us re-map channel positions to this car's ca654019 offline.
Writes log_raw_<timestamp>.csv into the GKFlasher dir (its cwd).

2026-09-08: the whole session is wrapped in a reconnect loop. A single K-line
read timeout used to end the capture (354 s into the first burble drive); now
the bus is closed, the ECU given a few seconds, and the connect/security/
identify sequence re-run. Each reconnect starts a new log_raw_*.csv, so a
drive may produce several files; stitch by timestamp. Ctrl-C ends the run."""
import os, sys, time, traceback
GKDIR = r"C:\Users\megaw\OneDrive\hyundai-tuning\tools\GKFlasher"
os.environ["PYTHONUTF8"] = "1"
os.chdir(GKDIR)
sys.path.insert(0, GKDIR)
import gkflasher
from flasher.logging import logger_raw
# main() calls the module-global `logger(ecu)` when args.logger is set; swap it.
gkflasher.logger = logger_raw
sys.argv = ["gkflasher.py", "--protocol", "kline", "--interface", "COM7", "--logger"]
config, args = gkflasher.load_arguments()

attempt = 0
while True:
    attempt += 1
    bus = None
    try:
        bus = gkflasher.initialize_bus(config["protocol"], config[config["protocol"]])
        gkflasher.main(bus, args)      # returns only on Ctrl-C inside logger_raw
        break
    except KeyboardInterrupt:
        break
    except Exception as e:             # TimeoutException, serial errors, KWP negatives
        print("\n[!] session dropped (attempt %d): %s" % (attempt, repr(e)))
        if attempt >= 200:
            traceback.print_exc()
            break
        try:
            if bus is not None:
                bus.close()
        except Exception:
            pass
        time.sleep(4)                  # let the ECU's diagnostic session time out
        print("[*] reconnecting..")
print("[*] logger finished")
