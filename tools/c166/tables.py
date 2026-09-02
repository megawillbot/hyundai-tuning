"""
Code-derived table geometry for SIMK43 ca654019.

The firmware accesses every calibration map through a 15-routine library at
file 0x44780-0x44B5E (physical 0xC4780-0xC4B5E).  Calling convention:

    MOV   R12, #<axis_addr - 0x8000>
    MOV   R13, <input value>
    CALLS 0x0C, <axis search>          ; -> index/fraction in RAM 0xFBE0-0xFBE6
    ... (second axis for 2-D tables)
    MOV   R12, #<table_addr - 0x8000>
    CALLS 0x0C, <lookup>               ; -> result in RL4 (8-bit z) or R4 (16-bit z)

Axis tables are stored as [count][breakpoint...]; the count is 2 bytes for
16-bit axes and 1 byte for 8-bit axes, and the XDF axis address is always the
first breakpoint, i.e. axis_table + 2 (or +1).

Element order is row-major: z[row_index * NCOLS + col_index], where NCOLS is
the number of X-axis breakpoints.

This module walks the disassembly, recovers each lookup site, and emits the
full geometry of every table the code actually reads.
"""
import sys, os, csv, json
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import Program, load_symbols, ROOT
from addrmodel import op_to_cal

# ---- the library ----------------------------------------------------------
# addr -> (role, axis_bits, interpolated)
AXIS_ROUTINES = {
    0x44780: ("Y", 16, True),
    0x447C8: ("Y", 8, True),
    0x44812: ("X", 8, True),
    0x44860: ("X", 16, True),
    0x44864: ("X", 16, True),      # same routine, entry past a stray MOV
    0x44A8A: ("X", 8, False),
    0x44AE4: ("Y", 8, False),
    0x44B10: ("Y", 16, False),
}
# addr -> (dims, z_bits, interpolated)
LOOKUP_ROUTINES = {
    0x448B6: (2, 8, True),
    0x449D4: (2, 16, True),
    0x449A2: (1, 8, True),
    0x44970: (1, 16, True),
    0x44B3C: (2, 8, False),
    0x44ACA: (2, 16, False),
    0x44B54: (1, 8, False),
    0x44ABE: (1, 16, False),
}

CAL_BIAS = 0x8000


class TableScanner:
    def __init__(self):
        self.p = Program()
        self.p.run()
        self.cal = self.p.cal
        self.syms = load_symbols()

    def u16(self, a):
        return self.cal[a] | (self.cal[a + 1] << 8)

    def axis_info(self, addr, bits):
        """Return (count, breakpoints, xdf_axis_addr) for an axis table."""
        if not (0x8000 <= addr < 0xDF40):
            return None
        if bits == 16:
            n = self.u16(addr)
            if not (1 <= n <= 64) or addr + 2 + 2 * n > 0xDF40:
                return None
            bp = [self.u16(addr + 2 + 2 * i) for i in range(n)]
            first = addr + 2
        else:
            n = self.cal[addr]
            if not (1 <= n <= 64) or addr + 1 + n > 0xDF40:
                return None
            bp = [self.cal[addr + 1 + i] for i in range(n)]
            first = addr + 1
        mono = all(bp[i] <= bp[i + 1] for i in range(len(bp) - 1))
        return dict(count=n, bp=bp, xdf_addr=first, monotonic=mono)

    def scan(self):
        """Walk the code recovering axis-search / lookup sequences.

        Axis results live in fixed RAM slots, so the firmware routinely
        searches an axis once and then performs several lookups against it.
        Pending axis state is therefore kept until overwritten by another
        search of the same role, and cleared only at function boundaries.
        """
        addrs = sorted(self.p.insns)
        entries = set(self.p.func_entries)
        sites = []
        pend = {}
        r12 = None
        r13 = None
        for a in addrs:
            i = self.p.insns[a]
            if a in entries:
                pend = {}; r12 = None; r13 = None
            if i.mnem == "MOV" and i.size == 4 and i.imm is not None                     and i.ops.startswith("R12,"):
                r12 = i.imm
                continue
            if i.ops.startswith("R13,"):
                r13 = (i.mnem, i.ops)
                continue
            if i.flow == "ret":
                pend = {}; r12 = None
                continue
            if i.flow == "call" and i.target is not None:
                t = i.target
                if t in AXIS_ROUTINES and op_to_cal(r12) is not None:
                    role, bits, interp = AXIS_ROUTINES[t]
                    pend[role] = dict(addr=op_to_cal(r12), bits=bits,
                                      interp=interp, input=r13, site=a)
                    r12 = None
                elif t in LOOKUP_ROUTINES and op_to_cal(r12) is not None:
                    dims, zb, interp = LOOKUP_ROUTINES[t]
                    sites.append(dict(
                        site=a, table=op_to_cal(r12), dims=dims, z_bits=zb,
                        interp=interp,
                        x=pend.get("X"), y=pend.get("Y")))
                    r12 = None
                elif t not in AXIS_ROUTINES and t not in LOOKUP_ROUTINES:
                    r12 = None
        return sites

    def geometry(self, sites):
        """Collapse per-site records into one record per table address."""
        by_table = defaultdict(list)
        for s in sites:
            by_table[s["table"]].append(s)
        out = {}
        for t, ss in by_table.items():
            s = ss[0]
            rec = dict(addr=t, dims=s["dims"], z_bits=s["z_bits"],
                       interp=s["interp"], n_sites=len(ss),
                       sites=[x["site"] for x in ss])
            if s["dims"] == 1:
                ax = s.get("y") or s.get("x")
                s = dict(s); s["x"] = ax; s["y"] = None
            for role in ("x", "y"):
                ax = s.get(role)
                if ax:
                    info = self.axis_info(ax["addr"], ax["bits"])
                    rec[role + "_axis"] = ax["addr"]
                    rec[role + "_bits"] = ax["bits"]
                    rec[role + "_input"] = ax["input"][1] if ax["input"] else ""
                    if info:
                        rec[role + "_count"] = info["count"]
                        rec[role + "_xdf"] = info["xdf_addr"]
                        rec[role + "_bp"] = info["bp"]
                        rec[role + "_mono"] = info["monotonic"]
            out[t] = rec
        return out


def main():
    ts = TableScanner()
    sites = ts.scan()
    geo = ts.geometry(sites)
    print("lookup call sites found : %d" % len(sites))
    print("distinct tables         : %d" % len(geo))
    d = Counter((g["dims"], g["z_bits"], g["interp"]) for g in geo.values())
    for k, v in sorted(d.items()):
        print("   %dD  z=%2dbit  %s : %d" % (k[0], k[1], "interp" if k[2] else "step ", v))

    known = sum(1 for a in geo if a in ts.syms)
    print("tables also in the derived symbol map : %d / %d" % (known, len(geo)))

    # geometry agreement with the map
    agree = dis = 0
    for a, g in geo.items():
        v = ts.syms.get(a)
        if not v or v.get("kind") != "table":
            continue
        rows, cols = v.get("rows"), v.get("cols")
        gr = g.get("y_count", 1)
        gc = g.get("x_count", 1)
        if rows == gr and cols == gc:
            agree += 1
        else:
            dis += 1
    print("geometry matches symbol map : %d agree, %d differ" % (agree, dis))

    out = os.environ.get("SCRATCH", ".")
    rows_out = []
    for a in sorted(geo):
        g = geo[a]
        v = ts.syms.get(a, {})
        rows_out.append(dict(
            addr="0x%04X" % a, symbol=v.get("sym", ""),
            dims=g["dims"], z_bits=g["z_bits"],
            mode="interp" if g["interp"] else "step",
            rows=g.get("y_count", ""), cols=g.get("x_count", ""),
            y_axis=("0x%04X" % g["y_axis"]) if "y_axis" in g else "",
            y_xdf=("0x%04X" % g["y_xdf"]) if "y_xdf" in g else "",
            y_bits=g.get("y_bits", ""), y_input=g.get("y_input", ""),
            x_axis=("0x%04X" % g["x_axis"]) if "x_axis" in g else "",
            x_xdf=("0x%04X" % g["x_xdf"]) if "x_xdf" in g else "",
            x_bits=g.get("x_bits", ""), x_input=g.get("x_input", ""),
            n_sites=g["n_sites"],
            code_sites=";".join("%05X" % s for s in g["sites"][:8]),
        ))
    p = os.path.join(out, "table_geometry.csv")
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
        w.writeheader(); w.writerows(rows_out)
    print("wrote", p)
    json.dump({("0x%04X" % k): {kk: vv for kk, vv in v.items() if kk != "sites"}
               for k, v in geo.items()},
              open(os.path.join(out, "table_geometry.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
