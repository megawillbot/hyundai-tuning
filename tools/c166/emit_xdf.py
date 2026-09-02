"""
Emit a TunerPro XDF from code-derived table geometry.

This is a *reading and exploration* definition, like the extended XDF but
sourced from the disassembly rather than from ca652048 alignment. Its value is
the ~150 tables the alignment method could not place -- most importantly the
main and secondary fuel maps and the modelled-EGT map, which sit in the
high-address region the alignment covers only sparsely.

Every table here has:
  * geometry certified by the interpolation call that reads it (dims, element
    width, interpolated vs stepped)
  * both axes wired to the real breakpoint arrays the code passes
  * a provisional name from its axis-driver signature

Scaling is deliberately left raw (equation X). The code proves shape and axes;
it does not hand us engineering units without more work. Decode against a
datalog before trusting any value, and never flash a table edited here without
the checksum step.
"""
import sys, os, json, re, html

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import Program, load_symbols, ROOT
from addrmodel import CAL_START, CAL_END

# RAM inputs identified from axis breakpoint scaling + the __N_32/__MAF
# symbol-name convention. See docs/code-derived-tables.md.
INPUT_NAME = {
    0xF564: "rpm",
    0xC59E: "rpm/32",
    0xF500: "load(MAF)",
    0xF501: "load",
    0xF502: "load2",
    0xC53F: "temp/idx",
    0xC543: "temp/idx2",
    0xC544: "temp/idx3",
    0xF496: "tps_grad",
    0xF497: "tps_grad2",
    0xF4DA: "pedal",
    0xE039: "state",
}

# A few high-confidence semantic names for the flagship code-only maps.
NAMED = {
    0xD3A8: "FUEL_MAIN_ti__N__MAF",
    0xD528: "FUEL_ALT_ti__N__MAF",
    0xCA24: "EGT_model__N_32__MAF",
    0xCAB0: "EGT_model_2__N_32__MAF",
}


def input_of(ops):
    m = re.search(r"\[0x([0-9A-Fa-f]+)\]", ops or "")
    if not m:
        return None
    return int(m.group(1), 16)


def provisional_name(a, g):
    if a in NAMED:
        return NAMED[a]
    parts = []
    yi = input_of(g.get("y_input", ""))
    xi = input_of(g.get("x_input", ""))
    tag = "IP" if g["interp"] else "ID"
    stem = "map%04X" % a
    yl = INPUT_NAME.get(yi, "y") if g["dims"] == 2 else None
    xl = INPUT_NAME.get(xi, "x")
    if g["dims"] == 2:
        return "%s_%s__%s_%s" % (tag, stem, yl, xl)
    return "%s_%s__%s" % (tag, stem, xl)


def axis_labels(cal, xdf_addr, bits, count):
    out = []
    for i in range(count):
        if bits == 16:
            v = cal[xdf_addr + 2 * i] | (cal[xdf_addr + 2 * i + 1] << 8)
        else:
            v = cal[xdf_addr + i]
        out.append(v)
    return out


def emit():
    p = Program(); p.run()
    cal = p.cal
    syms = load_symbols()
    geo = json.load(open(os.path.join(os.environ.get("SCRATCH", "."),
                                      "table_geometry.json")))

    tables = []
    uid = 0x9000
    for k in sorted(geo, key=lambda x: int(x, 16)):
        a = int(k, 16)
        g = geo[k]
        in_map = a in syms
        name = syms[a]["sym"] if in_map else provisional_name(a, g)
        rows = g.get("y_count", 1) if g["dims"] == 2 else 1
        cols = g.get("x_count", 1)
        if g["dims"] == 1:
            rows, cols = 1, g.get("x_count", g.get("y_count", 1))
        zbits = g["z_bits"]
        uid += 1

        # axes
        def axis_xml(role_key, cnt_key, xdf_key, bits_key, axis_id, n):
            addr = g.get(xdf_key)
            bits = g.get(bits_key)
            drv = input_of(g.get(role_key + "_input", ""))
            label = INPUT_NAME.get(drv, "")
            if addr and bits:
                labels = axis_labels(cal, addr, bits, n)
                lab_xml = "\n".join(
                    '      <LABEL index="%d" value="%d" />' % (i, v)
                    for i, v in enumerate(labels))
                units = html.escape(label)
                return ('    <XDFAXIS id="%s" uniqueid="0x0">\n'
                        '      <indexcount>%d</indexcount>\n'
                        '      <units>%s</units>\n'
                        '%s\n'
                        '      <MATH equation="X"><VAR id="X" /></MATH>\n'
                        '    </XDFAXIS>' % (axis_id, n, units, lab_xml))
            # fallback index axis
            lab_xml = "\n".join('      <LABEL index="%d" value="%d" />' % (i, i)
                                for i in range(n))
            return ('    <XDFAXIS id="%s" uniqueid="0x0">\n'
                    '      <indexcount>%d</indexcount>\n%s\n'
                    '      <MATH equation="X"><VAR id="X" /></MATH>\n'
                    '    </XDFAXIS>' % (axis_id, n, lab_xml))

        x_axis = axis_xml("x", "x_count", "x_xdf", "x_bits", "x", cols)
        if g["dims"] == 2:
            y_axis = axis_xml("y", "y_count", "y_xdf", "y_bits", "y", rows)
        else:
            y_axis = ('    <XDFAXIS id="y" uniqueid="0x0">\n'
                      '      <indexcount>1</indexcount>\n'
                      '      <LABEL index="0" value="0" />\n'
                      '      <MATH equation="X"><VAR id="X" /></MATH>\n'
                      '    </XDFAXIS>')

        mode = "interp" if g["interp"] else "stepped"
        src = "in symbol map" if in_map else "CODE-ONLY (not in symbol map)"
        allff = all(cal[a + i] == 0xFF for i in range(rows * cols * (zbits // 8)))
        desc = ("[code-derived] %s, %s, %d-bit %s. sites: %s.%s"
                % (src, mode, zbits,
                   "%dx%d" % (rows, cols),
                   ";".join("%05X" % s for s in g.get("sites", [])[:4]),
                   " ALL-FF in our cal (disabled feature)." if allff else ""))

        # mmedtypeflags 0x02 = LSB-first (little-endian); the C167 is
        # little-endian, so 16-bit cells MUST carry it or TunerPro reads them
        # byte-swapped (big-endian). 8-bit needs no flag.
        zflag = ' mmedtypeflags="0x02"' if zbits == 16 else ''
        z = ('    <XDFAXIS id="z">\n'
             '      <EMBEDDEDDATA%s mmedaddress="0x%04X" mmedelementsizebits="%d" '
             'mmedrowcount="%d" mmedcolcount="%d" mmedmajorstridebits="0" '
             'mmedminorstridebits="0" />\n'
             '      <units></units>\n'
             '      <decimalpl>0</decimalpl>\n'
             '      <outputtype>1</outputtype>\n'
             '      <MATH equation="X"><VAR id="X" /></MATH>\n'
             '    </XDFAXIS>' % (zflag, a, zbits, rows, cols))

        tables.append(
            '  <XDFTABLE uniqueid="0x%X" flags="0x30">\n'
            '    <title>%s</title>\n'
            '    <description>%s</description>\n'
            '    <CATEGORYMEM index="0" category="1" />\n'
            '%s\n%s\n%s\n'
            '  </XDFTABLE>' % (uid, html.escape(name), html.escape(desc),
                              x_axis, y_axis, z))

    header = (
        '<!-- code-derived exploration XDF for SIMK43 ca654019.\n'
        '     Auto-generated from the disassembly by tools/c166/emit_xdf.py.\n'
        '     Geometry and axes are certified by the interpolation calls that\n'
        '     read each table; scaling is raw (equation X) and names are\n'
        '     provisional. See docs/code-derived-tables.md. Do NOT flash edits\n'
        '     from here without the checksum step. -->\n')
    xml = ('<XDFFORMAT version="1.60">\n'
           '  <XDFHEADER>\n'
           '    <flags>0x1</flags>\n'
           '    <description>ca654019 code-derived tables (exploration)</description>\n'
           '    <BASEOFFSET offset="0" subtract="0" />\n'
           '    <REGION type="0xFFFFFFFF" startaddress="0x8000" size="0x5F40" '
           'regionflags="0x0" name="Calibration" desc="" />\n'
           '  </XDFHEADER>\n'
           + "\n".join(tables) + "\n</XDFFORMAT>\n")

    out = os.path.join(ROOT, "defs", "ca654019 2700 code-derived.xdf")
    open(out, "w", encoding="utf-8").write(header + xml)
    print("wrote", out)
    print("tables:", len(tables))
    return out


if __name__ == "__main__":
    emit()
