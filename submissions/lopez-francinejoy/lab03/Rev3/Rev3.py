"""Standalone Rev. 3 3D structural model with units, materials, and member sizes (Excel report)."""

import io
import math
import os
import zipfile
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

try:
    from openpyxl.drawing.image import Image as ExcelImage
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
except ImportError as exc:
    raise RuntimeError("pandas, matplotlib, and openpyxl are required") from exc

OUTPUT_DIR = Path(__file__).resolve().parent
OUT_XLSX = OUTPUT_DIR / "cube_structure_rev3.xlsx"
OUT_PNG = OUTPUT_DIR / "cube_structure_rev3.png"
REV = "Rev. 3"
L = 6.0
NODES = {
    1: (0.0, 0.0, 0.0), 2: (L, 0.0, 0.0), 3: (L, 0.0, L),
    4: (0.0, 0.0, L), 5: (0.0, L, 0.0), 6: (L, L, 0.0),
    7: (L, L, L), 8: (0.0, L, L),
}
MEMBERS = [("M1", 1, 2), ("M2", 2, 3), ("M3", 3, 4), ("M4", 4, 1),
           ("M5", 5, 6), ("M6", 6, 7), ("M7", 7, 8), ("M8", 8, 5),
           ("M9", 1, 5), ("M10", 2, 6), ("M11", 3, 7), ("M12", 4, 8)]
GLOBAL_DOFS = ["DX", "DY", "DZ", "RX", "RY", "RZ"]
RESTRAINED = ["DX", "DY", "DZ"]
RELEASES = {"M1": ("P", "P"), "M4": ("P", "P"), "M9": ("P", "R"),
            "M10": ("P", "R"), "M11": ("P", "R"), "M12": ("P", "R")}

# ------------------------------------------------------------------
# Rev. 3 — Unit system, material library, member-size (section) library
# All three libraries are loaded directly from the provided ZIP files
# (Units.zip, Material.zip, Member Size.zip) so the ZIP data stays the
# single authoritative source.
# ------------------------------------------------------------------

UNIT_SYSTEM_NAME = "Imperial"          # "Imperial" or "Standard Metric"


def _xlsx_from_zip(zipname):
    """Open the first .xlsx found inside a ZIP as a pandas ExcelFile."""
    with zipfile.ZipFile(OUTPUT_DIR / zipname) as zf:
        member = next(n for n in zf.namelist() if n.lower().endswith(".xlsx"))
        return pd.ExcelFile(io.BytesIO(zf.read(member)))


def load_unit_library():
    """Unit systems + conversion factors from Units/Units_Imperial_Metric.xlsx."""
    df = _xlsx_from_zip("Units.zip").parse("Conversion Factors", header=9)
    df = df.dropna(subset=[df.columns[0]])
    factors = {}
    for _, row in df.iterrows():
        quantity = str(row.iloc[0]).strip()
        if quantity in ("Quantity", "NaN") or not isinstance(row.iloc[3], (int, float)):
            continue
        factors[quantity] = {
            "imperial": str(row.iloc[1]).strip(),
            "metric": str(row.iloc[2]).strip(),
            "imp_to_metric": float(row.iloc[3]),
        }
    systems = {
        "Imperial": {
            "length": "ft", "section dim": "in", "area": "in\u00b2",
            "moment of inertia": "in\u2074", "force": "kip", "moment": "kip\u00b7ft",
        },
        "Standard Metric": {
            "length": "m", "section dim": "mm", "area": "mm\u00b2",
            "moment of inertia": "mm\u2074", "force": "kN", "moment": "kN\u00b7m",
        },
    }
    return systems, factors


UNIT_SYSTEMS, UNIT_FACTORS = load_unit_library()


def load_material_library():
    """Material library from Material/RISA_Materials_Library.xlsx ('All Materials' sheet)."""
    df = _xlsx_from_zip("Material.zip").parse("All Materials", header=3)
    df = df.dropna(subset=[df.columns[1]])
    df = df[df.columns[:8].append(df.columns[9:])]
    materials = {}
    for _, row in df.iterrows():
        label = str(row.iloc[1]).strip()
        if label.lower() in ("nan", "label", ""):
            continue
        def _num(i):
            if i >= len(row):
                return None
            value = row.iloc[i]
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        materials[label] = {
            "type": str(row.iloc[0]).strip(),
            "E_ksi": _num(2), "G_ksi": _num(3),
            "Nu": _num(4), "therm_1e-5_F": _num(5),
            "density_kcf": _num(6),
            "Fy_ksi": _num(7),
            "Fu_ksi": _num(8),
            "E_MPa": _num(9), "G_MPa": _num(10),
            "therm_1e-6_C": _num(11),
            "density_kNm3": _num(12),
            "Fy_MPa": _num(14),
            "Fu_MPa": _num(15),
        }
    return materials


MATERIALS = load_material_library()


def load_section_library():
    """Member-size library from Member Size/aisc-shapes-database-v160-2.xlsx (AISC v16.0)."""
    df = _xlsx_from_zip("Member Size.zip").parse("Database v16.0")
    df = df.dropna(subset=["AISC_Manual_Label"])
    sections = {}
    for _, row in df.iterrows():
        sections[str(row["AISC_Manual_Label"]).upper()] = {
            "type": row["Type"], "A_in2": float(row["A"]),
            "Ix_in4": float(row["Ix"]), "Iy_in4": float(row["Iy"]),
            "Zx_in3": float(row["Zx"]) if pd.notna(row["Zx"]) else None,
        }
    return sections


SECTIONS = load_section_library()

# Per-member-type assignments (NOT global): each member type keeps its own
# material and section so future models can mix materials/sections freely.
MEMBER_MATERIAL = {"Column": "A36 Gr.36", "Roof Beam": "A36 Gr.36", "Tie Beam": "A36 Gr.36"}
MEMBER_SECTION = {"Column": "W10X33", "Roof Beam": "W14X22", "Tie Beam": "W12X26"}


def validate_model():
    """Rev. 3 validation: unit system, materials, sections."""
    if UNIT_SYSTEM_NAME not in UNIT_SYSTEMS:
        raise ValueError(f"Unknown unit system: {UNIT_SYSTEM_NAME!r}")
    if "A36 Gr.36" not in MATERIALS:
        raise ValueError("A36 Gr.36 missing from material library")
    for kind, material in MEMBER_MATERIAL.items():
        if material not in MATERIALS:
            raise ValueError(f"{kind}: unknown material {material!r}")
    for kind, section in MEMBER_SECTION.items():
        if section not in SECTIONS:
            raise ValueError(f"{kind}: unknown section {section!r}")


def convert(value, quantity):
    """Convert an Imperial-solver value to the selected unit system's unit."""
    if UNIT_SYSTEM_NAME == "Imperial":
        return value, UNIT_FACTORS[quantity]["imperial"]
    return value * UNIT_FACTORS[quantity]["imp_to_metric"], UNIT_FACTORS[quantity]["metric"]
FERN_GREEN = "#3E8241"
PISTACHIO = "#8CD18E"
LIGHT_GREEN = "#9AE69C"
LAVENDER_FLORAL = "#BA98F5"
ROYAL_PURPLE = "#6948A3"
DEEP_PURPLE = "#4B2A73"
SOFT_PURPLE = "#E8DDF7"
WHITE = "#FFFFFF"
INK = ROYAL_PURPLE


def member_type(name, ni, nj):
    if NODES[ni][1] != NODES[nj][1]:
        return "Column"
    return "Roof Beam" if name in {"M5", "M6", "M7", "M8"} else "Tie Beam"


def local_axes(ni, nj, beta=0.0):
    start, end = np.array(NODES[ni]), np.array(NODES[nj])
    direction = end - start
    length = float(np.linalg.norm(direction))
    a1 = direction / length
    reference = np.array([0.0, 1.0, 0.0])
    if abs(float(np.dot(a1, reference))) > 0.999:
        reference = np.array([0.0, 0.0, 1.0])
    a3 = np.cross(a1, reference); a3 /= np.linalg.norm(a3)
    a2 = np.cross(a3, a1); angle = math.radians(beta)
    c, s = math.cos(angle), math.sin(angle)
    return length, a1, a2 * c + a3 * s, -a2 * s + a3 * c


def build_tables():
    validate_model()
    dofs, nodes, supports, incidences, axes, releases, materials, sections = [], [], [], [], [], [], [], []
    index = 0
    for nid, (x, y, z) in NODES.items():
        restrained = y == 0.0
        active = []
        first = index + 1
        for label in GLOBAL_DOFS:
            is_restrained = restrained and label in RESTRAINED
            if not is_restrained:
                index += 1; active.append(label)
            dofs.append({"Node": nid, "DOF": label, "DOF Type": "Translation" if label.startswith("D") else "Rotation",
                         "Active": not is_restrained, "Restrained": is_restrained,
                         "Global DOF #": index if not is_restrained else "-"})
        nodes.append({"Node": nid, "X (m)": x, "Y (m)": y, "Z (m)": z,
                      "Support": "Pinned" if restrained else "None",
                      "DOF range": f"{first}-{index + 3}" if restrained else f"{first}-{index + 6}",
                      "Active DOFs": ", ".join(active)})
        if restrained:
            supports.append({"Node": nid, "Support": "Pinned", "Restrained DOFs": ", ".join(RESTRAINED),
                             "Released DOFs": "RX, RY, RZ"})
    for name, ni, nj in MEMBERS:
        kind = member_type(name, ni, nj); beta = 90.0 if kind == "Column" else 0.0
        length, a1, a2, a3 = local_axes(ni, nj, beta)
        rel_i, rel_j = RELEASES.get(name, ("R", "R"))
        material_label = MEMBER_MATERIAL[kind]
        section_label = MEMBER_SECTION[kind]
        mat = MATERIALS[material_label]
        sec = SECTIONS[section_label]
        sec_a, area_unit = convert(sec["A_in2"], "Area")
        sec_ix, inertia_unit = convert(sec["Ix_in4"], "Moment of inertia")
        length_val, length_unit = convert(length, "Length")
        incidences.append({"Member": name, "Member Type": kind, "i": ni, "j": nj,
                           f"Length ({length_unit})": round(length_val, 4), "Beta (deg)": beta,
                           "Material": material_label, "Section": section_label,
                           f"A ({area_unit})": round(sec_a, 4), f"Ix ({inertia_unit})": round(sec_ix, 4),
                           f"E ({'ksi' if UNIT_SYSTEM_NAME == 'Imperial' else 'MPa'})": mat["E_ksi"] if UNIT_SYSTEM_NAME == "Imperial" else mat["E_MPa"]})
        sections.append({"Member Type": kind, "Section": section_label, "Material": material_label,
                         f"A ({area_unit})": round(sec_a, 4), f"Ix ({inertia_unit})": round(sec_ix, 4)})
        materials.append({"Member Type": kind, "Material": material_label, "E": mat["E_ksi"] if UNIT_SYSTEM_NAME == "Imperial" else mat["E_MPa"],
                          "Nu": mat["Nu"], "Fy": mat["Fy_ksi"] if UNIT_SYSTEM_NAME == "Imperial" else mat["Fy_MPa"]})
        axes.append({"Member": name, "Member Type": kind, "Beta (deg)": beta, "Local X": ", ".join(f"{v:.4f}" for v in a1), "Local Y": ", ".join(f"{v:.4f}" for v in a2), "Local Z": ", ".join(f"{v:.4f}" for v in a3)})
        releases.append({"Member": name, "Member Type": kind, "End i release": rel_i, "End j release": rel_j, "Released component": "Moment-Z (MZ)" if "P" in (rel_i, rel_j) else "None", "Pinned?": "Yes" if "P" in (rel_i, rel_j) else "No"})
    return *(pd.DataFrame(value) for value in (dofs, nodes, supports, incidences, axes, releases)), index, \
        pd.DataFrame(materials), pd.DataFrame(sections)


def draw_model():
    fig = plt.figure(figsize=(16, 9), facecolor=WHITE)
    ax = fig.add_axes([0.04, 0.08, 0.62, 0.80], projection="3d")
    ax.set_facecolor("#F8F6FC")
    for name, ni, nj in MEMBERS:
        kind = member_type(name, ni, nj); color = ROYAL_PURPLE if kind == "Column" else DEEP_PURPLE
        p, q = NODES[ni], NODES[nj]
        ax.plot3D([p[0], q[0]], [p[1], q[1]], [p[2], q[2]], color=color, lw=3.2)
        mid = (np.array(p) + np.array(q)) / 2
        beta = 90.0 if kind == "Column" else 0.0
        _, a1, a2, a3 = local_axes(ni, nj, beta)
        ax.text(* (mid + [0, 0.15, 0]), f"{name} [MZ]" if "P" in RELEASES.get(name, ()) else name, color=DEEP_PURPLE, fontsize=8, ha="center", fontweight="bold")
        for vector, color_axis, label, size in ((a1, FERN_GREEN, "1", .55), (a2, PISTACHIO, "2", .45), (a3, LAVENDER_FLORAL, "3", .45)):
            tip = mid + vector * size; ax.plot3D([mid[0], tip[0]], [mid[1], tip[1]], [mid[2], tip[2]], color=color_axis, lw=1.8); ax.text(*tip, label, color=color_axis, fontsize=8)
        for end, code in ((ni, RELEASES.get(name, ("R", "R"))[0]), (nj, RELEASES.get(name, ("R", "R"))[1])):
            if code == "P": ax.scatter(*NODES[end], facecolors="none", edgecolors=ROYAL_PURPLE, s=75, linewidths=1.8)
    for nid, point in NODES.items():
        base = point[1] == 0.0; ax.scatter(*point, color=DEEP_PURPLE if base else LAVENDER_FLORAL, edgecolors=WHITE, s=52); first = (nid - 1) * 6 + 1; ax.text(*point, f"N{nid}\nDOF {first}-{first + 5}", color=DEEP_PURPLE, fontsize=8)
        if base:
            x, y, z = point; apex = (x, y - .72, z); left = (x - .4, y - .18, z); right = (x + .4, y - .18, z); ax.add_collection3d(Poly3DCollection([[apex, left, right]], facecolors=ROYAL_PURPLE, edgecolors=DEEP_PURPLE))
    origin = np.array([0., 0., 0.])
    for vector, color, label in (([1, 0, 0], ROYAL_PURPLE, "Xg"), ([0, 1, 0], FERN_GREEN, "Yg"), ([0, 0, 1], LAVENDER_FLORAL, "Zg")):
        tip = origin + np.array(vector) * 1.4; ax.plot3D([0, tip[0]], [0, tip[1]], [0, tip[2]], color=color, lw=2); ax.text(*tip, label, color=color, fontweight="bold")
    ax.set_xlabel("X (m) - lateral", color=ROYAL_PURPLE); ax.set_ylabel("Y (m) - vertical", color=FERN_GREEN); ax.set_zlabel("Z (m) - lateral", color=LAVENDER_FLORAL)
    ax.set_title(f"6m x 6m x 6m Cube - Structural Model, {REV}\nPinned supports, local/global axes, beta angles, MZ releases, materials, and sections", color=DEEP_PURPLE, fontweight="bold")
    legend = [Line2D([0], [0], color=ROYAL_PURPLE, lw=3, label="Beam"), Line2D([0], [0], color=FERN_GREEN, lw=3, label="Column"), Line2D([0], [0], marker="o", color=WHITE, markerfacecolor=ROYAL_PURPLE, label="Supported node"), Line2D([0], [0], marker="o", color=WHITE, markerfacecolor=LIGHT_GREEN, label="Free node"), Line2D([0], [0], marker="o", color=WHITE, markerfacecolor="none", markeredgecolor=ROYAL_PURPLE, label="Pinned end (MZ released)"), Line2D([0], [0], color=FERN_GREEN, label="Local X"), Line2D([0], [0], color=PISTACHIO, label="Local Y"), Line2D([0], [0], color=LAVENDER_FLORAL, label="Local Z"), Line2D([0], [0], color=ROYAL_PURPLE, label="Global X"), Line2D([0], [0], color=FERN_GREEN, label="Global Y"), Line2D([0], [0], color=LAVENDER_FLORAL, label="Global Z")]
    ax.legend(handles=legend, loc="upper left", fontsize=8, ncol=2, facecolor=WHITE, edgecolor=ROYAL_PURPLE, framealpha=0.95)
    panel = f"MODEL DATA - {REV.upper()}\n\nUnit system\n  Selected        {UNIT_SYSTEM_NAME}\n\nGeometry\n  Cube edge       6.0 m\n  Nodes           8\n  Members         12\n\nSupports\n  Type            pinned\n  Nodes           1, 2, 3, 4\n  Restrained      DX, DY, DZ\n  Released        RX, RY, RZ\n\nNode degrees of freedom\n  DOF per node    6\n  Total DOF       48\n  Active DOF      36\n\nMaterials (per member type)\n" + "\n".join(f"  {kind:<13} {MEMBER_MATERIAL[kind]}" for kind in ("Column", "Roof Beam", "Tie Beam")) + "\n\nSections (AISC v16.0)\n" + "\n".join(f"  {kind:<13} {MEMBER_SECTION[kind]}" for kind in ("Column", "Roof Beam", "Tie Beam")) + "\n\nMember end releases\n  Component       Moment about local Z\n\nBeta angles\n  Base/Roof beam  0 deg\n  Column          90 deg"
    fig.text(.70, .90, panel, va="top", family="monospace", fontsize=9, bbox={"boxstyle": "round,pad=.7", "facecolor": "#F8F6FC", "edgecolor": ROYAL_PURPLE})
    fig.subplots_adjust(left=.02, right=.98, top=.90, bottom=.05)
    return fig


def write_excel(frames, total_dof, diagram):
    dof, nodes, supports, incidences, axes, releases, material_table, section_table = frames
    details = pd.DataFrame([
        {"Model item": "Unit system", "Value": UNIT_SYSTEM_NAME},
        {"Model item": "Geometry", "Value": "6 m x 6 m x 6 m cube"}, {"Model item": "Supports", "Value": "Pinned at nodes 1-4; DX, DY, DZ restrained"}, {"Model item": "Node DOFs", "Value": "DX, DY, DZ, RX, RY, RZ"}, {"Model item": "Total DOFs", "Value": total_dof}, {"Model item": "Active DOFs", "Value": 36}, {"Model item": "Local axes", "Value": "X axial, Y strong, Z weak / MZ"}, {"Model item": "Global axes", "Value": "X lateral, Y vertical, Z lateral"}, {"Model item": "Pinned beam behavior", "Value": "Pinned-in-X releases Moment-Z (MZ)"}, {"Model item": "Beta angles", "Value": "Beams 0 deg; columns 90 deg"},
    ])
    sheets = {"Summary": pd.DataFrame([{"Item": "Model", "Value": "6m x 6m x 6m cube (Rev. 3)"}, {"Item": "Unit System", "Value": UNIT_SYSTEM_NAME}, {"Item": "Members", "Value": 12}, {"Item": "Supports", "Value": "Pinned nodes 1-4"}, {"Item": "Total DOFs", "Value": total_dof}]), "Model Details": details, "Nodes": nodes, "Node DOFs": dof, "Supports": supports, "Incidences": incidences, "Member Local Axes": axes, "Member End Releases": releases, "Member Materials": material_table, "Member Sections": section_table}
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        for name, frame in sheets.items(): frame.to_excel(writer, sheet_name=name, index=False)
        wb = writer.book
        header_fill = PatternFill("solid", fgColor=ROYAL_PURPLE.lstrip("#"))
        title_fill = PatternFill("solid", fgColor=DEEP_PURPLE.lstrip("#"))
        band_fill = PatternFill("solid", fgColor=SOFT_PURPLE.lstrip("#"))
        header_font = Font(bold=True, color=WHITE.lstrip("#"), size=10)
        title_font = Font(bold=True, color=WHITE.lstrip("#"), size=13)
        thin = Side(style="thin", color="D8CDEE")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        tab_colors = [DEEP_PURPLE, ROYAL_PURPLE, LAVENDER_FLORAL, SOFT_PURPLE]
        for sheet_index, ws in enumerate(wb.worksheets):
            ws.insert_rows(1)
            max_column = max(1, ws.max_column)
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max_column)
            title = ws.cell(1, 1)
            title.value = f"{REV.upper()} STRUCTURAL MODEL - {ws.title.upper()}"
            title.font = title_font
            title.fill = title_fill
            title.alignment = Alignment(horizontal="left", vertical="center")
            ws.row_dimensions[1].height = 24
            ws.sheet_properties.tabColor = tab_colors[sheet_index % len(tab_colors)].lstrip("#")
            for column in range(1, max_column + 1):
                cell = ws.cell(2, column)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = border
            ws.row_dimensions[2].height = 30
            ws.freeze_panes = "A3"
            for row in range(3, ws.max_row + 1):
                for column in range(1, max_column + 1):
                    cell = ws.cell(row, column)
                    cell.border = border
                    cell.alignment = Alignment(horizontal="left" if column == 1 else "center", vertical="center", wrap_text=True)
                    if row % 2 == 1:
                        cell.fill = band_fill
            for column in range(1, max_column + 1):
                letter = get_column_letter(column)
                longest = max(len(str(ws.cell(row, column).value or "")) for row in range(1, ws.max_row + 1))
                ws.column_dimensions[letter].width = min(max(longest + 3, 12), 36)
            ws.auto_filter.ref = f"A2:{get_column_letter(max_column)}{ws.max_row}"
        ws = wb.create_sheet("Structural Diagram")
        ws.sheet_properties.tabColor = LAVENDER_FLORAL.lstrip("#")
        ws["A1"] = f"{REV.upper()} 3D STRUCTURAL MODEL"
        ws["A1"].font = Font(bold=True, size=14, color=DEEP_PURPLE.lstrip("#"))
        ws["A3"] = "Pinned supports, local/global axes, beta angles, node DOFs, and Moment-Z releases"
        ws["A3"].alignment = Alignment(wrap_text=True)
        image = ExcelImage(str(diagram)); image.width = 900; image.height = 650; ws.add_image(image, "A5")
        ws.column_dimensions["A"].width = 32
    print(f"Excel workbook written: {OUT_XLSX}")


def main():
    frames = build_tables(); *tables, total, material_table, section_table = frames
    tables = tables + [material_table, section_table]
    figure = draw_model()
    figure.savefig(OUT_PNG, dpi=200)
    global OUT_XLSX
    try:
        with open(OUT_XLSX, "ab"):
            pass
    except PermissionError:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        OUT_XLSX = OUTPUT_DIR / f"cube_structure_rev3_{stamp}.xlsx"
    write_excel(tables, total, OUT_PNG)
    print(f"Structural diagram saved: {OUT_PNG}")
    backend = plt.get_backend().lower()
    show_model = os.environ.get("REV3_SHOW", "1") != "0"
    if show_model and backend not in {"agg", "pdf", "svg", "ps", "template"}:
        plt.show()
    else:
        plt.close(figure)


if __name__ == "__main__":
    main()
