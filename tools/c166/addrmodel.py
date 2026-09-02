"""
SIMK43 ca654019 address model.

Established 2026-09-03 from the firmware itself.  The routine at file 0x43956
ends with, literally:

    MOV DPP0, #0x0022      ; page 0x22 -> physical 0x88000
    MOV DPP2, #0x0023      ; page 0x23 -> physical 0x8C000

and those two page registers are what every calibration access goes through.
A C166 16-bit data address selects a DPP by its top two bits, so:

    operand 0x0000-0x3FFF  DPP0=0x22  -> phys 0x88000+op  -> cal file op + 0x8000
    operand 0x4000-0x7FFF  DPP1       -> not calibration (RAM / other)
    operand 0x8000-0xBFFF  DPP2=0x23  -> phys 0x8C000+..  -> cal file op + 0x4000
    operand 0xC000-0xFFFF  DPP3=3     -> RAM 0xC000-0xDFFF, XRAM 0xE000-0xEFFF,
                                         ESFR 0xF000, IRAM 0xF200, SFR 0xFC00+

Measured enrichment against the independently derived symbol map:
    window 0x0000-0x3FFF, bias +0x8000 : 10.4x (all symbols), 9.2x (tables)
    window 0x8000-0xBFFF, bias +0x4000 : 21.9x (tables)
    window 0x4000-0x7FFF               : no enrichment at either bias
"""

CAL_START, CAL_END = 0x8000, 0xDF40
CODE_START, CODE_END = 0x10000, 0x4A6A6


def op_to_cal(op):
    """Map a 16-bit data operand to a calibration file offset, or None."""
    if op is None:
        return None
    if 0x0000 <= op < 0x4000:
        c = op + 0x8000
    elif 0x8000 <= op < 0xC000:
        c = op + 0x4000
    else:
        return None
    return c if CAL_START <= c < CAL_END else None


def cal_to_ops(cal):
    """Every operand that could address this calibration offset."""
    out = []
    if 0x8000 <= cal < 0xC000:
        out.append(cal - 0x8000)
    if 0xC000 <= cal < 0x10000:
        out.append(cal - 0x4000)
    return out


def phys(file_off):
    """File offset -> C167 physical address."""
    return file_off + 0x80000
