"""Read-only RAM + raw-frame logger (KWP 0x23 ReadMemoryByAddress alongside the
RDBLI 0x01 block). Same connect path as raw_logger.py. Built 2026-09-19 to read
the ECU's own TPS cells ([[closed-throttle-recognition]]):
  0xF496 processed TPS, 0xF498 raw TPS, 0xF49D debounced raw,
  0xF4C0/1 learned closed (8.8), 0xFD0A flags (bit 12 = closed throttle),
  0xFD46 flags (bit 0 = throttle open).
Writes log_ram_<timestamp>.csv in the GKFlasher dir:
  ms, hex of 0xF490..0xF4CF, hex of 0xFD00..0xFD4F, raw RDBLI frame hex.
Nothing is written to the ECU."""
import os, sys, time, csv, traceback
from datetime import datetime
GKDIR = r"C:\Users\megaw\OneDrive\hyundai-tuning\tools\GKFlasher"
os.environ["PYTHONUTF8"] = "1"
os.chdir(GKDIR)
sys.path.insert(0, GKDIR)
import gkflasher
from flasher.logging import poll_raw
from gkbus.protocol.kwp2000.commands import ReadMemoryByAddress, StartDiagnosticSession
from gkbus.protocol.kwp2000.enums import DiagnosticSession

DRIVE = False
FRAME_EVERY = 1   # read the (slow) RDBLI sensor frame every Nth row
SHIFT = False
BLOCKS = [(0xF490, 0x40), (0xFD00, 0x50)]
if "puc" in sys.argv:   # overrun-cut view: inhibit levels/state, injector mask word, engine state
    sys.argv.remove("puc")
    BLOCKS = [(0xC1A8, 8), (0xFD00, 0x50), (0xF9BA, 2), (0xC20B, 5)]
if "drive" in sys.argv:   # everything at ~1 Hz: TPS cells, flags (FD52 faults, FD64), inhibit/CAN-TPS/state (C1A8..C20F), ignition chain
    sys.argv.remove("drive")
    BLOCKS = [(0xF490, 0x40), (0xFD00, 0x70), (0xC1A8, 0x68), (0xC320, 0x28)]
    DRIVE = True
if "shift" in sys.argv:   # fast (~2.5 Hz) gear-shift torque-reduction view: ignition chain + C58B..C59F
    sys.argv.remove("shift")    # (C592 = GS counter -> M_FD26.2, C59A, C59E = rpm/32); sensor frame every 8th row
    BLOCKS = [(0xC320, 0x28), (0xC58B, 0x15)]
    FRAME_EVERY = 8
    SHIFT = True
if "iga" in sys.argv:   # ignition view: angle chain C320..C347, E10A.. words, engine state, F9BA mask
    sys.argv.remove("iga")
    BLOCKS = [(0xC320, 0x28), (0xE10A, 8), (0xF9BA, 2), (0xC20B, 5)]

def rd(ecu, addr, size):
    return bytes(ecu.bus.execute(ReadMemoryByAddress(offset=addr, size=size)).get_data())

def ram_logger(ecu):
    # probe 0x23 on RAM in the session main() leaves us in, then in DEFAULT
    try:
        print("[*] RAM probe (current session):", rd(ecu, 0xF496, 3).hex())
    except Exception as e:
        print("[!] RAM probe failed in current session:", repr(e))
    ecu.bus.execute(StartDiagnosticSession(DiagnosticSession.DEFAULT, ecu.get_desired_baudrate().index))
    try:
        print("[*] RAM probe (default session):", rd(ecu, 0xF496, 3).hex())
    except Exception as e:
        print("[!] RAM probe failed in default session:", repr(e))
        raise KeyboardInterrupt
    fn = "log_shift_{}.csv".format(datetime.now().strftime("%Y-%m-%d_%H%M%S")) if SHIFT else "log_drive_{}.csv".format(datetime.now().strftime("%Y-%m-%d_%H%M%S")) if DRIVE else {0xC1A8: "log_puc_{}.csv", 0xC320: "log_iga_{}.csv"}.get(BLOCKS[0][0], "log_ram_{}.csv").format(datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    print("[*] Logging to", fn)
    with open(fn, "w", newline="") as f:
        w = csv.writer(f)
        i = 0
        try:
            while True:
                row = [int(time.time() * 1000)]
                for a, n in BLOCKS:
                    row.append(rd(ecu, a, n).hex())
                row.append(bytes(poll_raw(ecu)[0]).hex() if i % FRAME_EVERY == 0 else "")
                w.writerow(row)
                i += 1
                if i % (10 if FRAME_EVERY > 1 else 5) == 0:
                    f.flush()
                    print("frames:", i)
        except KeyboardInterrupt:
            pass

gkflasher.logger = ram_logger
sys.argv = ["gkflasher.py", "--protocol", "kline", "--interface", "COM7", "--logger"]
config, args = gkflasher.load_arguments()
attempt = 0
while True:
    attempt += 1
    bus = None
    try:
        bus = gkflasher.initialize_bus(config["protocol"], config[config["protocol"]])
        gkflasher.main(bus, args)
        break
    except KeyboardInterrupt:
        break
    except Exception as e:
        print("\n[!] session dropped (attempt %d): %s" % (attempt, repr(e)))
        if attempt >= 400:
            traceback.print_exc()
            break
        try:
            if bus is not None:
                bus.close()
        except Exception:
            pass
        time.sleep(4)
        print("[*] reconnecting..")
print("[*] ram logger finished")
