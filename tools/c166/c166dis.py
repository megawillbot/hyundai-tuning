"""
C166/C167 disassembler for Siemens SIMK4x ECU firmware.

Written for the Hyundai Tiburon GK 2.7 SIMK43 (Infineon C167) program zone.
No public C166 disassembler was available, so this implements the Infineon
C166 instruction set directly.

Address model
-------------
The SIMK43 V6 4mbit flash dump is 512 KiB.  GKFlasher / the OpenGK Ghidra
loader place it in the C167 24-bit space as:

    file 0x08000..0x0FFFF  ->  0x88000  calibration  (segment 8)
    file 0x10000..0x4A6A6  ->  0x90000  program code (segments 9..C)

With the DPP registers holding 0x22/0x23 for DPP2/DPP3, the 16-bit data
addresses the code emits for calibration accesses are numerically equal to
the calibration *file offsets* (0x8000-0xDF40), which is what the XDF and
the derived symbol map use.  That makes raw 16-bit operands directly
comparable to table addresses.

Usage:
    from c166dis import Disassembler, Insn
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

# --------------------------------------------------------------------------
# operand helpers
# --------------------------------------------------------------------------

CC = ["cc_UC", "cc_NET", "cc_Z", "cc_NZ", "cc_V", "cc_NV", "cc_N", "cc_NN",
      "cc_C", "cc_NC", "cc_SGT", "cc_SLE", "cc_SLT", "cc_SGE", "cc_UGT", "cc_ULE"]

# SFR names at 0xFE00 + 2*reg  (reg 0x00-0xEF), core set only
SFR = {
    0x00: "DPP0", 0x01: "DPP1", 0x02: "DPP2", 0x03: "DPP3", 0x04: "CSP",
    0x06: "MDH", 0x07: "MDL", 0x08: "CP", 0x09: "SP", 0x0A: "STKOV",
    0x0B: "STKUN", 0x0E: "CPUCON1", 0x0F: "CPUCON2",
    0x10: "ADDRSEL1", 0x11: "ADDRSEL2", 0x12: "ADDRSEL3", 0x13: "ADDRSEL4",
    0x40: "T2", 0x41: "T3", 0x42: "T4", 0x43: "T5", 0x44: "T6",
    0x45: "CAPREL", 0x46: "T0", 0x47: "T1", 0x48: "T01CON",
    0x49: "CCM0", 0x4A: "CCM1", 0x4B: "CCM2", 0x4C: "CCM3",
    0x4D: "T2CON", 0x4E: "T3CON", 0x4F: "T4CON",
    0x50: "T5CON", 0x51: "T6CON", 0x52: "PECC0", 0x53: "PECC1",
    0x58: "S0TBUF", 0x59: "S0RBUF", 0x5A: "S0BG",
    0x60: "PSW", 0x61: "SYSCON", 0x62: "BUSCON0", 0x63: "MDC",
    0x64: "S0CON", 0x65: "ADCON", 0x66: "WDTCON", 0x67: "WDT",
    0x68: "ADDAT", 0x6A: "P0L", 0x6B: "P0H", 0x6C: "P1L", 0x6D: "P1H",
    0x70: "P2", 0x71: "DP2", 0x72: "P3", 0x73: "DP3", 0x74: "P4",
    0x75: "DP4", 0x76: "P5", 0x78: "P6", 0x79: "DP6", 0x7A: "P7",
    0x7B: "DP7", 0x7C: "P8", 0x7D: "DP8",
    0x80: "ADDAT2", 0x86: "T7", 0x87: "T8", 0x88: "T7IC", 0x89: "T8IC",
    0x8E: "ZEROS", 0x8F: "ONES",
}


def reg_name(r: int, byte: bool = False) -> str:
    """Decode an 8-bit `reg` operand."""
    if r >= 0xF0:
        n = r - 0xF0
        if byte:
            return ("RL%d" % (n >> 1)) if (n & 1) == 0 else ("RH%d" % (n >> 1))
        return "R%d" % n
    if r in SFR:
        return SFR[r]
    return "SFR_%04X" % (0xFE00 + 2 * r)


def bitaddr_name(b: int) -> str:
    """C166 bit-addressable operand: 0x00-0x7F -> RAM 0xFD00+2n,
    0x80-0xEF -> SFR 0xFF00+2(n-0x80), 0xF0-0xFF -> GPR."""
    if b >= 0xF0:
        return "R%d" % (b - 0xF0)
    if b >= 0x80:
        a = 0xFF00 + 2 * (b - 0x80)
        return SFR_BITADDR.get(a, "SFR_%04X" % a)
    return "M_%04X" % (0xFD00 + 2 * b)


SFR_BITADDR = {
    0xFF10: "PSW", 0xFF12: "SYSCON", 0xFF0C: "BUSCON0", 0xFF0E: "MDC",
    0xFFB0: "S0CON", 0xFFA0: "ADCON", 0xFFAE: "WDTCON",
    0xFF00: "T2CON", 0xFF02: "T3CON", 0xFF04: "T4CON", 0xFF06: "T5CON",
    0xFF08: "T6CON", 0xFF0A: "CAPREL",
    0xFFC0: "P2", 0xFFC2: "DP2", 0xFFC4: "P3", 0xFFC6: "DP3", 0xFFC8: "P4",
    0xFFCA: "DP4", 0xFFCC: "P5", 0xFFD0: "P6", 0xFFD2: "DP6",
    0xFF14: "TFR", 0xFF16: "ISNC",
}


def s8(v: int) -> int:
    return v - 256 if v & 0x80 else v


# --------------------------------------------------------------------------
# instruction record
# --------------------------------------------------------------------------

@dataclass
class Insn:
    addr: int                       # file offset
    size: int
    mnem: str
    ops: str = ""
    raw: bytes = b""
    # semantic annotations used by the analyser
    target: Optional[int] = None    # branch/call target (file offset) if intra-segment
    seg_target: Optional[int] = None  # absolute 24-bit target for JMPS/CALLS
    mem: Optional[int] = None       # 16-bit memory operand, if any
    imm: Optional[int] = None       # immediate value, if any
    flow: str = "next"              # next | jump | cond | call | ret | trap | undef
    dst_reg: Optional[int] = None   # word GPR index written, when obvious
    src_reg: Optional[int] = None

    def __str__(self):
        return "%05X  %-14s %-34s %s" % (
            self.addr, self.raw.hex(" "), self.mnem + (" " + self.ops if self.ops else ""), "")


# --------------------------------------------------------------------------
# core decoder
# --------------------------------------------------------------------------

ALU = {0x0: "ADD", 0x1: "ADDC", 0x2: "SUB", 0x3: "SUBC",
       0x4: "CMP", 0x5: "XOR", 0x6: "AND", 0x7: "OR"}

BITOP4 = {0x0A: "BFLDL", 0x1A: "BFLDH", 0x2A: "BCMP", 0x3A: "BMOVN",
          0x4A: "BMOV", 0x5A: "BOR", 0x6A: "BAND", 0x7A: "BXOR"}


class Disassembler:
    def __init__(self, data: bytes, base: int = 0):
        self.d = data
        self.base = base

    def u8(self, a):
        return self.d[a]

    def u16(self, a):
        return self.d[a] | (self.d[a + 1] << 8)

    # -- indirect operand for the x8/x9 column --------------------------------
    @staticmethod
    def _ind(m: int, byte=False) -> Tuple[str, Optional[int]]:
        if m & 0x8:
            i = m & 0x3
            if m & 0x4:
                return "[R%d+]" % i, None
            return "[R%d]" % i, None
        return "#%d" % (m & 0x7), (m & 0x7)

    def decode(self, a: int) -> Insn:
        d = self.d
        if a + 1 >= len(d):
            return Insn(a, 1, "DB", "0x%02X" % d[a], d[a:a + 1], flow="undef")
        op = d[a]
        b1 = d[a + 1]
        hi, lo = op >> 4, op & 0xF
        n, m = b1 >> 4, b1 & 0xF
        raw2 = d[a:a + 2]
        raw4 = d[a:a + 4]

        def I(size, mnem, ops="", **kw):
            return Insn(a, size, mnem, ops, d[a:a + size], **kw)

        # ---- ALU column ----------------------------------------------------
        if lo in (0x0, 0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0x7, 0x8, 0x9) and hi <= 0x7:
            mn = ALU[hi]
            byte = lo in (0x1, 0x3, 0x5, 0x7, 0x9)
            b = "B" if byte else ""
            if lo in (0x0, 0x1):
                return I(2, mn + b, "%s, %s" % (reg_name(0xF0 + n, byte), reg_name(0xF0 + m, byte)),
                         dst_reg=n, src_reg=m)
            if lo in (0x2, 0x3):
                mem = self.u16(a + 2)
                return I(4, mn + b, "%s, [0x%04X]" % (reg_name(b1, byte), mem), mem=mem)
            if lo in (0x4, 0x5):
                mem = self.u16(a + 2)
                return I(4, mn + b, "[0x%04X], %s" % (mem, reg_name(b1, byte)), mem=mem)
            if lo in (0x6, 0x7):
                if byte:
                    return I(4, mn + b, "%s, #0x%02X" % (reg_name(b1, True), d[a + 2]), imm=d[a + 2])
                v = self.u16(a + 2)
                return I(4, mn + b, "%s, #0x%04X" % (reg_name(b1, False), v), imm=v)
            # 0x8 / 0x9
            s, iv = self._ind(m, byte)
            return I(2, mn + b, "%s, %s" % (reg_name(0xF0 + n, byte), s), dst_reg=n, imm=iv)

        # ---- CMPI/CMPD (0x80,0x90,0xA0,0xB0 and .2/.6) ----------------------
        if op in (0x80, 0x90, 0xA0, 0xB0):
            mn = {0x80: "CMPI1", 0x90: "CMPI2", 0xA0: "CMPD1", 0xB0: "CMPD2"}[op]
            return I(2, mn, "R%d, #%d" % (m, n), dst_reg=m, imm=n)
        if op in (0x82, 0x92, 0xA2, 0xB2):
            mn = {0x82: "CMPI1", 0x92: "CMPI2", 0xA2: "CMPD1", 0xB2: "CMPD2"}[op]
            mem = self.u16(a + 2)
            return I(4, mn, "%s, [0x%04X]" % (reg_name(b1), mem), mem=mem)
        if op in (0x86, 0x96, 0xA6, 0xB6):
            mn = {0x86: "CMPI1", 0x96: "CMPI2", 0xA6: "CMPD1", 0xB6: "CMPD2"}[op]
            v = self.u16(a + 2)
            return I(4, mn, "%s, #0x%04X" % (reg_name(b1), v), imm=v)

        # ---- NEG/CPL --------------------------------------------------------
        if op == 0x81:
            return I(2, "NEG", "R%d" % n, dst_reg=n)
        if op == 0x91:
            return I(2, "CPL", "R%d" % n, dst_reg=n)
        if op == 0xA1:
            return I(2, "NEGB", reg_name(0xF0 + n, True))
        if op == 0xB1:
            return I(2, "CPLB", reg_name(0xF0 + n, True))

        # ---- MUL / DIV / PRIOR ---------------------------------------------
        if op == 0x0B:
            return I(2, "MUL", "R%d, R%d" % (n, m))
        if op == 0x1B:
            return I(2, "MULU", "R%d, R%d" % (n, m))
        if op == 0x2B:
            return I(2, "PRIOR", "R%d, R%d" % (n, m))
        if op in (0x4B, 0x5B, 0x6B, 0x7B):
            mn = {0x4B: "DIV", 0x5B: "DIVU", 0x6B: "DIVL", 0x7B: "DIVLU"}[op]
            return I(2, mn, "R%d" % n)

        # ---- shifts ---------------------------------------------------------
        SH = {0x0C: ("ROL", 0), 0x1C: ("ROL", 1), 0x2C: ("ROR", 0), 0x3C: ("ROR", 1),
              0x4C: ("SHL", 0), 0x5C: ("SHL", 1), 0x6C: ("SHR", 0), 0x7C: ("SHR", 1),
              0xAC: ("ASHR", 0), 0xBC: ("ASHR", 1)}
        if op in SH:
            mn, imm = SH[op]
            if imm:
                # operand byte: data4 in high nibble, register in low nibble
                return I(2, mn, "R%d, #%d" % (m, n), dst_reg=m, imm=n)
            return I(2, mn, "R%d, R%d" % (n, m), dst_reg=n)

        # ---- MOV family -----------------------------------------------------
        if op == 0xF0:
            return I(2, "MOV", "R%d, R%d" % (n, m), dst_reg=n, src_reg=m)
        if op == 0xF1:
            return I(2, "MOVB", "%s, %s" % (reg_name(0xF0 + n, True), reg_name(0xF0 + m, True)))
        if op == 0xE0:
            return I(2, "MOV", "R%d, #0x%X" % (m, n), dst_reg=m, imm=n)
        if op == 0xE1:
            return I(2, "MOVB", "%s, #0x%X" % (reg_name(0xF0 + m, True), n), imm=n)
        if op == 0xE6:
            v = self.u16(a + 2)
            return I(4, "MOV", "%s, #0x%04X" % (reg_name(b1), v), imm=v,
                     dst_reg=(b1 - 0xF0) if b1 >= 0xF0 else None)
        if op == 0xE7:
            return I(4, "MOVB", "%s, #0x%02X" % (reg_name(b1, True), d[a + 2]), imm=d[a + 2])
        if op == 0xF2:
            mem = self.u16(a + 2)
            return I(4, "MOV", "%s, [0x%04X]" % (reg_name(b1), mem), mem=mem,
                     dst_reg=(b1 - 0xF0) if b1 >= 0xF0 else None)
        if op == 0xF3:
            mem = self.u16(a + 2)
            return I(4, "MOVB", "%s, [0x%04X]" % (reg_name(b1, True), mem), mem=mem)
        if op == 0xF6:
            mem = self.u16(a + 2)
            return I(4, "MOV", "[0x%04X], %s" % (mem, reg_name(b1)), mem=mem)
        if op == 0xF7:
            mem = self.u16(a + 2)
            return I(4, "MOVB", "[0x%04X], %s" % (mem, reg_name(b1, True)), mem=mem)
        if op == 0xA8:
            return I(2, "MOV", "R%d, [R%d]" % (n, m), dst_reg=n)
        if op == 0xA9:
            return I(2, "MOVB", "%s, [R%d]" % (reg_name(0xF0 + n, True), m))
        if op == 0x98:
            return I(2, "MOV", "R%d, [R%d+]" % (n, m), dst_reg=n)
        if op == 0x99:
            return I(2, "MOVB", "%s, [R%d+]" % (reg_name(0xF0 + n, True), m))
        if op == 0xB8:
            return I(2, "MOV", "[R%d], R%d" % (m, n))
        if op == 0xB9:
            return I(2, "MOVB", "[R%d], %s" % (m, reg_name(0xF0 + n, True)))
        if op == 0x88:
            return I(2, "MOV", "[-R%d], R%d" % (m, n))
        if op == 0x89:
            return I(2, "MOVB", "[-R%d], %s" % (m, reg_name(0xF0 + n, True)))
        if op == 0xC8:
            return I(2, "MOV", "[R%d], [R%d]" % (n, m))
        if op == 0xC9:
            return I(2, "MOVB", "[R%d], [R%d]" % (n, m))
        if op == 0xD8:
            return I(2, "MOV", "[R%d+], [R%d]" % (n, m))
        if op == 0xD9:
            return I(2, "MOVB", "[R%d+], [R%d]" % (n, m))
        if op == 0xE8:
            return I(2, "MOV", "[R%d], [R%d+]" % (n, m))
        if op == 0xE9:
            return I(2, "MOVB", "[R%d], [R%d+]" % (n, m))
        if op == 0xD4:
            v = self.u16(a + 2)
            return I(4, "MOV", "R%d, [R%d+#0x%04X]" % (n, m, v), imm=v, mem=v, dst_reg=n)
        if op == 0xF4:
            v = self.u16(a + 2)
            return I(4, "MOVB", "%s, [R%d+#0x%04X]" % (reg_name(0xF0 + n, True), m, v), imm=v, mem=v)
        if op == 0xC4:
            v = self.u16(a + 2)
            return I(4, "MOV", "[R%d+#0x%04X], R%d" % (m, v, n), imm=v, mem=v)
        if op == 0xE4:
            v = self.u16(a + 2)
            return I(4, "MOVB", "[R%d+#0x%04X], %s" % (m, v, reg_name(0xF0 + n, True)), imm=v, mem=v)
        if op == 0x84:
            mem = self.u16(a + 2)
            return I(4, "MOV", "[R%d], [0x%04X]" % (m, mem), mem=mem)
        if op == 0x94:
            mem = self.u16(a + 2)
            return I(4, "MOV", "[0x%04X], [R%d]" % (mem, m), mem=mem)
        if op == 0xA4:
            mem = self.u16(a + 2)
            return I(4, "MOVB", "[R%d], [0x%04X]" % (m, mem), mem=mem)
        if op == 0xB4:
            mem = self.u16(a + 2)
            return I(4, "MOVB", "[0x%04X], [R%d]" % (mem, m), mem=mem)

        # ---- MOVBZ / MOVBS --------------------------------------------------
        # NOTE: MOVBZ/MOVBS reg-reg form is encoded "mn", not "nm" --
        # low nibble is the word destination, high nibble the byte source.
        if op == 0xC0:
            return I(2, "MOVBZ", "R%d, %s" % (m, reg_name(0xF0 + n, True)), dst_reg=m)
        if op == 0xD0:
            return I(2, "MOVBS", "R%d, %s" % (m, reg_name(0xF0 + n, True)), dst_reg=m)
        if op == 0xC2:
            mem = self.u16(a + 2)
            return I(4, "MOVBZ", "%s, [0x%04X]" % (reg_name(b1), mem), mem=mem,
                     dst_reg=(b1 - 0xF0) if b1 >= 0xF0 else None)
        if op == 0xD2:
            mem = self.u16(a + 2)
            return I(4, "MOVBS", "%s, [0x%04X]" % (reg_name(b1), mem), mem=mem,
                     dst_reg=(b1 - 0xF0) if b1 >= 0xF0 else None)
        if op == 0xC5:
            mem = self.u16(a + 2)
            return I(4, "MOVBZ", "[0x%04X], %s" % (mem, reg_name(b1, True)), mem=mem)
        if op == 0xD5:
            mem = self.u16(a + 2)
            return I(4, "MOVBS", "[0x%04X], %s" % (mem, reg_name(b1, True)), mem=mem)

        # ---- bit field / bit test ops (xA column) ---------------------------
        if op in BITOP4:
            return I(4, BITOP4[op], "0x%02X, 0x%02X, 0x%02X" % (b1, d[a + 2], d[a + 3]))
        if op in (0x8A, 0x9A, 0xAA, 0xBA):
            mn = {0x8A: "JB", 0x9A: "JNB", 0xAA: "JBC", 0xBA: "JNBS"}[op]
            rel = s8(d[a + 2])
            tgt = a + 4 + 2 * rel
            bitaddr = b1
            bitno = d[a + 3] >> 4
            return I(4, mn, "%s.%d, 0x%05X" % (bitaddr_name(bitaddr), bitno, tgt),
                     target=tgt, flow="cond")
        if lo == 0xE:
            return I(2, "BCLR", "%s.%d" % (bitaddr_name(b1), hi))
        if lo == 0xF:
            return I(2, "BSET", "%s.%d" % (bitaddr_name(b1), hi))

        # ---- control flow ---------------------------------------------------
        if lo == 0xD:
            rel = s8(b1)
            tgt = a + 2 + 2 * rel
            return I(2, "JMPR", "%s, 0x%05X" % (CC[hi], tgt), target=tgt,
                     flow="jump" if hi == 0 else "cond")
        if op == 0xCA:   # CALLA cc, caddr
            tgt = self.u16(a + 2)
            cc = b1 >> 4
            return I(4, "CALLA", "%s, 0x%04X" % (CC[cc], tgt), target=self._seg_of(a, tgt),
                     flow="call")
        if op == 0xEA:   # JMPA cc, caddr
            tgt = self.u16(a + 2)
            cc = b1 >> 4
            return I(4, "JMPA", "%s, 0x%04X" % (CC[cc], tgt), target=self._seg_of(a, tgt),
                     flow="jump" if cc == 0 else "cond")
        if op == 0xDA:   # CALLS seg, caddr
            seg = b1
            off = self.u16(a + 2)
            return I(4, "CALLS", "0x%02X, 0x%04X" % (seg, off),
                     seg_target=(seg << 16) | off, target=self._abs(seg, off), flow="call")
        if op == 0xFA:   # JMPS seg, caddr
            seg = b1
            off = self.u16(a + 2)
            return I(4, "JMPS", "0x%02X, 0x%04X" % (seg, off),
                     seg_target=(seg << 16) | off, target=self._abs(seg, off), flow="jump")
        if op == 0xBB:
            rel = s8(b1)
            tgt = a + 2 + 2 * rel
            return I(2, "CALLR", "0x%05X" % tgt, target=tgt, flow="call")
        if op == 0xAB:
            return I(2, "CALLI", "%s, [R%d]" % (CC[n], m), flow="call")
        if op == 0x9C:
            return I(2, "JMPI", "%s, [R%d]" % (CC[n], m), flow="jump" if n == 0 else "cond")
        if op == 0xE2:
            tgt = self.u16(a + 2)
            return I(4, "PCALL", "%s, 0x%04X" % (reg_name(b1), tgt),
                     target=self._seg_of(a, tgt), flow="call")
        if op == 0xCB:
            return I(2, "RET", "", flow="ret")
        if op == 0xDB:
            return I(2, "RETS", "", flow="ret")
        if op == 0xFB:
            return I(2, "RETI", "", flow="ret")
        if op == 0xEB:
            return I(4, "RETP", reg_name(b1), flow="ret")
        if op == 0x9B:
            return I(2, "TRAP", "#0x%02X" % (b1 >> 1), flow="trap")

        # ---- misc -----------------------------------------------------------
        if op == 0xCC:
            return I(2, "NOP")
        if op == 0xEC:
            return I(4, "PUSH", reg_name(b1))
        if op == 0xFC:
            return I(4, "POP", reg_name(b1))
        if op == 0xC6:
            v = self.u16(a + 2)
            return I(4, "SCXT", "%s, #0x%04X" % (reg_name(b1), v), imm=v)
        if op == 0xD6:
            mem = self.u16(a + 2)
            return I(4, "SCXT", "%s, [0x%04X]" % (reg_name(b1), mem), mem=mem)
        if op == 0xD1:
            irang = ((b1 >> 4) & 3) + 1
            return I(2, "EXTR" if (b1 & 0x80) else "ATOMIC", "#%d" % irang, imm=irang)
        if op == 0xDC:
            irang = ((b1 >> 4) & 3) + 1
            mn = ("EXTPR" if (b1 & 0x40) else "EXTSR") if (b1 & 0x80) else \
                 ("EXTP" if (b1 & 0x40) else "EXTS")
            return I(2, mn, "R%d, #%d" % (b1 & 0xF, irang), imm=irang)
        if op == 0xD7:
            irang = ((b1 >> 4) & 3) + 1
            page_hi = b1 & 0x3
            val = d[a + 2] | (page_hi << 8)
            mn = ("EXTPR" if (b1 & 0x40) else "EXTSR") if (b1 & 0x80) else \
                 ("EXTP" if (b1 & 0x40) else "EXTS")
            if b1 & 0x40:
                return I(4, mn, "#0x%03X, #%d" % (val, irang), imm=val)
            return I(4, mn, "#0x%02X, #%d" % (d[a + 2], irang), imm=d[a + 2])
        if op == 0xA5 and d[a + 1] == 0x5A:
            return I(4, "DISWDT")
        if op == 0xB5 and d[a + 1] == 0x4A:
            return I(4, "EINIT")
        if op == 0xA7 and d[a + 1] == 0x58:
            return I(4, "SRVWDT")
        if op == 0xB7 and d[a + 1] == 0x48:
            return I(4, "SRST", "", flow="jump")
        if op == 0x87 and d[a + 1] == 0x78:
            return I(4, "IDLE")
        if op == 0x97 and d[a + 1] == 0x68:
            return I(4, "PWRDN")

        return I(2, "??", "0x%02X 0x%02X" % (op, b1), flow="undef")

    # -- segment helpers -----------------------------------------------------
    def _seg_of(self, a: int, off: int) -> Optional[int]:
        """Intra-segment target: keep the segment of the current address."""
        phys = a + 0x80000
        seg = phys >> 16
        return ((seg << 16) | off) - 0x80000

    def _abs(self, seg: int, off: int) -> Optional[int]:
        return ((seg << 16) | off) - 0x80000


# --------------------------------------------------------------------------
# linear sweep validation helper
# --------------------------------------------------------------------------

def sweep(dis: Disassembler, start: int, end: int) -> List[Insn]:
    out = []
    a = start
    while a < end:
        i = dis.decode(a)
        out.append(i)
        a += i.size
    return out


if __name__ == "__main__":
    import sys
    data = open(sys.argv[1], "rb").read()
    s = int(sys.argv[2], 16)
    e = int(sys.argv[3], 16)
    dis = Disassembler(data)
    for i in sweep(dis, s, e):
        print(i)
