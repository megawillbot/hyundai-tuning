"""
Calibration cross-reference database for SIMK43 ca654019.

Address model: see addrmodel.py.  Two calibration windows are in use --
operands 0x0000-0x3FFF via DPP0=0x22 (bias +0x8000) and 0x8000-0xBFFF via
DPP2=0x23 (bias +0x4000).

Emits, for every calibration byte that code touches, the instruction(s) that
touch it and the enclosing function.
"""
import sys, os, json, re, csv, bisect
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from c166dis import Disassembler
from analyze import Program, load_symbols, CODE_START, CODE_END, CAL_START, CAL_END, ROOT
from addrmodel import op_to_cal

CAL_BIAS = 0x8000          # operand -> calibration file offset
OPERAND_MAX = 0x8000       # operands >= this are RAM/SFR, not calibration


class Xref:
    def __init__(self):
        self.p = Program()
        self.funcs, _ = self.p.run()
        self.func_starts = sorted(self.funcs)
        self.syms = load_symbols()
        self.ranges = self._ranges()

    # -- map an instruction address to its enclosing discovered function ----
    def func_of(self, addr):
        i = bisect.bisect_right(self.func_starts, addr) - 1
        return self.func_starts[i] if i >= 0 else None

    def _ranges(self):
        items = sorted((a, v) for a, v in self.syms.items())
        out = []
        for idx, (a, v) in enumerate(items):
            declared = a + max(1, v.get("size", 1))
            nxt = items[idx + 1][0] if idx + 1 < len(items) else CAL_END
            out.append((a, min(declared, nxt), v))
        self._starts = [r[0] for r in out]
        return out

    def sym_at(self, cal_addr):
        i = bisect.bisect_right(self._starts, cal_addr) - 1
        if i < 0:
            return None, None
        s, e, v = self.ranges[i]
        if s <= cal_addr < e:
            return v, cal_addr - s
        return None, None

    # -- the main extraction ------------------------------------------------
    def build(self):
        direct = defaultdict(list)     # cal addr -> [(insn addr, mnem, ops)]
        pointer = defaultdict(list)    # cal addr loaded as an immediate
        for a, i in sorted(self.p.insns.items()):
            c = op_to_cal(i.mem)
            if c is not None:
                direct[c].append((a, i.mnem, i.ops))
            if i.imm is not None and i.mnem == "MOV" and i.size == 4:
                c = op_to_cal(i.imm)
                if c is not None:
                    pointer[c].append((a, i.mnem, i.ops))
        return direct, pointer


def main():
    x = Xref()
    direct, pointer = x.build()
    print("functions            : %d" % len(x.funcs))
    print("instructions         : %d" % len(x.p.insns))
    print("direct cal operands  : %d distinct, %d refs"
          % (len(direct), sum(len(v) for v in direct.values())))
    print("immediate cal ptrs   : %d distinct, %d refs"
          % (len(pointer), sum(len(v) for v in pointer.values())))

    named = sum(1 for a in direct if x.sym_at(a)[0])
    exact = sum(1 for a in direct if a in x.syms)
    print("direct refs landing inside a mapped symbol : %d / %d (%.1f%%)"
          % (named, len(direct), 100 * named / len(direct)))
    print("   ... exactly on its first byte           : %d (%.1f%%)"
          % (exact, 100 * exact / len(direct)))

    out = os.environ.get("SCRATCH", ".")
    rows = []
    for a in sorted(set(direct) | set(pointer)):
        v, off = x.sym_at(a)
        rows.append(dict(
            cal_addr="0x%04X" % a,
            symbol=(v["sym"] if v else ""),
            sym_offset=(off if off is not None else ""),
            kind=(v["kind"] if v else ""),
            tier=(v.get("tier", "") if v else ""),
            n_direct=len(direct.get(a, [])),
            n_ptr=len(pointer.get(a, [])),
            code_refs=";".join("%05X" % r[0] for r in
                               (direct.get(a, []) + pointer.get(a, []))[:12]),
            funcs=";".join(sorted({"%05X" % (x.func_of(r[0]) or 0) for r in
                                   (direct.get(a, []) + pointer.get(a, []))})[:12]),
        ))
    p = os.path.join(out, "cal_xrefs.csv")
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("wrote", p, len(rows), "rows")

    json.dump({"direct": {("0x%04X" % k): [r[0] for r in v] for k, v in direct.items()},
               "pointer": {("0x%04X" % k): [r[0] for r in v] for k, v in pointer.items()},
               "funcs": sorted(x.funcs)},
              open(os.path.join(out, "xrefs.json"), "w"))


if __name__ == "__main__":
    main()
