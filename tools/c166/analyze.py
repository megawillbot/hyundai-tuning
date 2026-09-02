"""
C166 program-zone analyser for SIMK43 ca654019.

Builds:
  * an instruction map (recursive descent seeded by discovered call targets)
  * a function list
  * a call graph
  * calibration cross-references (16-bit data operands landing in 0x8000-0xDF40)

Run:  python analyze.py            (writes JSON to the scratchpad)
"""
import sys, os, json, re
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from c166dis import Disassembler, Insn

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BIN = os.path.join(ROOT, "roms", "stock", "PROGRAM_ca654019_read_2026-08-29.bin")
CAL = os.path.join(ROOT, "roms", "stock", "cal_ca654019_G5J7TS0A_read1.bin")

CODE_START, CODE_END = 0x10000, 0x4A6A6
CAL_START, CAL_END = 0x8000, 0xDF40


def load():
    return open(BIN, "rb").read(), open(CAL, "rb").read()


class Program:
    def __init__(self):
        self.data, self.cal = load()
        self.dis = Disassembler(self.data)
        self.insns = {}          # addr -> Insn
        self.func_entries = set()
        self.callers = defaultdict(set)   # callee -> {caller func}
        self.calls = defaultdict(set)     # func -> {callee}

    # ---- pass 1: seed entries from a linear sweep ------------------------
    def seed(self):
        a = CODE_START
        seeds = set()
        while a < CODE_END:
            i = self.dis.decode(a)
            if i.flow == "call" and i.target is not None \
                    and CODE_START <= i.target < CODE_END:
                seeds.add(i.target)
            a += i.size
        return seeds

    # ---- pass 2: recursive descent ---------------------------------------
    def descend(self, seeds):
        work = list(seeds)
        seen_funcs = set()
        while work:
            f = work.pop()
            if f in seen_funcs:
                continue
            seen_funcs.add(f)
            self.func_entries.add(f)
            stack = [f]
            local = set()
            while stack:
                a = stack.pop()
                if a in local or not (CODE_START <= a < CODE_END):
                    continue
                local.add(a)
                i = self.insns.get(a)
                if i is None:
                    i = self.dis.decode(a)
                    self.insns[a] = i
                if i.flow in ("ret", "trap", "undef"):
                    continue
                if i.flow == "jump":
                    if i.target is not None:
                        stack.append(i.target)
                    continue
                if i.flow == "cond" and i.target is not None:
                    stack.append(i.target)
                if i.flow == "call" and i.target is not None:
                    self.calls[f].add(i.target)
                    self.callers[i.target].add(f)
                    if CODE_START <= i.target < CODE_END and i.target not in seen_funcs:
                        work.append(i.target)
                stack.append(a + i.size)
        return seen_funcs

    # ---- fill gaps with a linear sweep -----------------------------------
    def fill(self):
        a = CODE_START
        while a < CODE_END:
            if a in self.insns:
                a += self.insns[a].size
                continue
            i = self.dis.decode(a)
            self.insns.setdefault(a, i)
            a += i.size

    def run(self):
        seeds = self.seed()
        funcs = self.descend(seeds)
        covered = sum(i.size for i in self.insns.values())
        self.fill()
        return funcs, covered


# --------------------------------------------------------------------------
# symbol map loading
# --------------------------------------------------------------------------

def load_symbols():
    """Return {addr: (symbol, kind, extra)} from the extended XDF + constants CSV."""
    syms = {}
    xdf = os.path.join(ROOT, "defs", "ca654019 2700 extended.xdf")
    txt = open(xdf, encoding="utf-8", errors="replace").read()
    for blk in re.finditer(r"<XDFTABLE\b.*?</XDFTABLE>", txt, re.S):
        b = blk.group()
        t = re.search(r"<title>(.*?)</title>", b)
        z = re.search(r'<XDFAXIS id="z">.*?mmedaddress="(0x[0-9A-Fa-f]+)"'
                      r'.*?mmedelementsizebits="(\d+)".*?mmedrowcount="(\d+)"'
                      r'.*?mmedcolcount="(\d+)"', b, re.S)
        eq = re.search(r'<XDFAXIS id="z">.*?<MATH equation="(.*?)"', b, re.S)
        d = re.search(r"<description>(.*?)</description>", b, re.S)
        if t and z:
            addr = int(z.group(1), 16)
            sz = int(z.group(2)) // 8 * int(z.group(3)) * int(z.group(4))
            syms[addr] = dict(sym=t.group(1), kind="table", size=sz,
                              rows=int(z.group(3)), cols=int(z.group(4)),
                              bits=int(z.group(2)),
                              eq=eq.group(1) if eq else "",
                              desc=d.group(1).strip() if d else "")
    csvp = os.path.join(ROOT, "docs", "ca654019-constants-map.csv")
    import csv as _csv
    with open(csvp, newline="", encoding="utf-8") as fh:
        for row in _csv.DictReader(fh):
            a = int(row["our_address"], 16)
            if a not in syms:
                syms[a] = dict(sym=row["symbol"], kind="const",
                               size=int(row["size_bytes"]), tier=row["tier"],
                               eq=row.get("equation", ""), desc=row.get("description", ""))
    return syms


def build_ranges(syms):
    """Sorted (start, end, sym) so an address can be attributed to a table interior."""
    items = sorted((a, v) for a, v in syms.items())
    out = []
    for idx, (a, v) in enumerate(items):
        end = a + max(1, v.get("size", 1))
        nxt = items[idx + 1][0] if idx + 1 < len(items) else CAL_END
        out.append((a, min(end, nxt), v["sym"], v))
    return out


def attribute(ranges, addr):
    import bisect
    starts = [r[0] for r in ranges]
    i = bisect.bisect_right(starts, addr) - 1
    if i < 0:
        return None
    s, e, sym, v = ranges[i]
    if s <= addr < e:
        return (sym, addr - s, v)
    return None


if __name__ == "__main__":
    p = Program()
    funcs, covered = p.run()
    print("functions discovered : %d" % len(funcs))
    print("bytes reached by recursive descent : %d / %d (%.1f%%)"
          % (covered, CODE_END - CODE_START,
             100 * covered / (CODE_END - CODE_START)))
    print("total instructions after fill : %d" % len(p.insns))
    und = [i for i in p.insns.values() if i.mnem == "??"]
    print("undefined opcodes : %d" % len(und))

    # ---- calibration cross references ----
    xref = defaultdict(list)
    for a, i in p.insns.items():
        if i.mem is not None and CAL_START <= i.mem < CAL_END:
            xref[i.mem].append(a)
    print("distinct cal addresses referenced : %d" % len(xref))
    print("total cal references              : %d" % sum(len(v) for v in xref.values()))

    syms = load_symbols()
    print("symbols loaded : %d" % len(syms))
    hits = sum(1 for m in xref if m in syms)
    print("referenced addresses that are a known symbol START : %d (%.1f%%)"
          % (hits, 100 * hits / max(1, len(xref))))

    out = os.environ.get("SCRATCH", ".")
    json.dump({"funcs": sorted(funcs),
               "xref": {("0x%04X" % k): v for k, v in xref.items()}},
              open(os.path.join(out, "analysis.json"), "w"))
    print("written", os.path.join(out, "analysis.json"))
