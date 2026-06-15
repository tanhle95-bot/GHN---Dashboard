"""
Shared data fetching module — reused by all cron jobs and the dashboard API.
Fetches Google Sheets XLSX and parses into structured data.
"""
import os
import urllib.request
import io
import zipfile
import xml.etree.ElementTree as ET

ALLOWED_SHEET_ID = os.environ.get('ALLOWED_SHEET_ID', '1Kjqwt6MIghCzfCSifVrpIpVHbC0o77lxMVVFlCZ26xY')
URL = f"https://docs.google.com/spreadsheets/d/{ALLOWED_SHEET_ID}/export?format=xlsx"

HANOI_KEYWORDS = ["Hà Nội", "HNO", "Long Biên", "Bắc Từ Liêm", "Thanh Oai",
                   "Hoài Đức", "Đức Long", "Thanh Trì", "Đông Anh"]
HANOI_KEYWORDS_LOWER = [kw.lower() for kw in HANOI_KEYWORDS]


def fast_parse_sheet(z, sheet_file, strings):
    """Parse a single sheet from XLSX zip into list of rows."""
    sheet_xml = z.read(sheet_file)
    root_sheet = ET.fromstring(sheet_xml)
    rows = []
    ns_sheet = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    for r in root_sheet.findall(".//ns:row", ns_sheet):
        row_cells = {}
        curr_col_idx = 0
        for c in r.findall("ns:c", ns_sheet):
            ref = c.get("r")
            if ref is not None:
                col_letter = "".join(filter(str.isalpha, ref))
                col_idx = 0
                for char in col_letter:
                    col_idx = col_idx * 26 + (ord(char) - ord("A") + 1)
                col_idx -= 1
                curr_col_idx = col_idx
            else:
                col_idx = curr_col_idx
            t = c.get("t")
            v_el = c.find("ns:v", ns_sheet)
            val = None
            if v_el is not None:
                v_text = v_el.text
                if t == "s":
                    try:
                        val = strings[int(v_text)] if v_text is not None else None
                    except (IndexError, ValueError, TypeError):
                        val = v_text
                elif t == "b":
                    val = v_text == "1"
                else:
                    try:
                        val = float(v_text) if v_text is not None and ("." in v_text or "e" in v_text.lower()) else int(v_text) if v_text is not None else None
                    except ValueError:
                        val = v_text
            row_cells[col_idx] = val
            curr_col_idx = col_idx + 1
        if row_cells:
            max_idx = max(row_cells.keys())
            row_list = [row_cells.get(i, None) for i in range(max_idx + 1)]
            rows.append(row_list)
    return rows


def load_workbook():
    """Download and parse the XLSX workbook. Returns (zipfile, strings, sheet_targets)."""
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    response = urllib.request.urlopen(req)
    excel_bytes = io.BytesIO(response.read())
    z = zipfile.ZipFile(excel_bytes)

    # Shared strings
    strings = []
    try:
        sst_xml = z.read("xl/sharedStrings.xml")
        root_sst = ET.fromstring(sst_xml)
        ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for t in root_sst.findall(".//ns:t", ns):
            strings.append(t.text)
    except KeyError:
        pass

    # Sheet name → file mapping
    wb_xml = z.read("xl/workbook.xml")
    root_wb = ET.fromstring(wb_xml)
    wb_rels_xml = z.read("xl/_rels/workbook.xml.rels")
    root_rels = ET.fromstring(wb_rels_xml)
    ns_rels = {"ns": "http://schemas.openxmlformats.org/package/2006/relationships"}
    rel_to_target = {}
    for rel in root_rels.findall(".//ns:Relationship", ns_rels):
        rel_to_target[rel.get("Id")] = rel.get("Target")

    namespaces = {
        "ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    }
    sheet_targets = {}
    for sheet in root_wb.findall(".//ns:sheet", namespaces):
        name = sheet.get("name")
        r_id = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rel_to_target[r_id]
        sheet_targets[name] = "xl/" + target

    return z, strings, sheet_targets


def is_hanoi_warehouse(name):
    """Check if warehouse name belongs to Hanoi region."""
    if not name:
        return False
    name_lower = str(name).lower()
    return "kho giao hàng nặng" in name_lower and any(kw in name_lower for kw in HANOI_KEYWORDS_LOWER)


def short_name(warehouse):
    """Shorten warehouse name for display."""
    return str(warehouse).replace('Kho Giao Hàng Nặng - ', '').replace(' - Hà Nội', '').replace('-Hà Nội', '')


def parse_gtc_data(z, sheet_targets, strings):
    """Parse GTC ratio data from raw_hieusuat sheet. Returns list of dicts."""
    if "raw_hieusuat" not in sheet_targets:
        return []

    rows = fast_parse_sheet(z, sheet_targets["raw_hieusuat"], strings)
    header = rows[0]
    col_wh = header.index("warehouse_name")
    col_sld = header.index("sld")
    col_sld_gtc = header.index("sld_gtc")

    groups = {}
    for row in rows[1:]:
        if not row or len(row) <= max(col_wh, col_sld, col_sld_gtc):
            continue
        wh_val = str(row[col_wh]) if row[col_wh] is not None else ""
        if is_hanoi_warehouse(wh_val):
            sld_val = float(row[col_sld]) if row[col_sld] is not None else 0.0
            sld_gtc_val = float(row[col_sld_gtc]) if row[col_sld_gtc] is not None else 0.0
            if wh_val not in groups:
                groups[wh_val] = {"total_assigned": 0.0, "total_success": 0.0}
            groups[wh_val]["total_assigned"] += sld_val
            groups[wh_val]["total_success"] += sld_gtc_val

    result = []
    for wh_name, vals in groups.items():
        total_assigned = vals["total_assigned"]
        total_success = vals["total_success"]
        gtc_ratio = (total_success / total_assigned * 100) if total_assigned > 0 else 0.0
        result.append({
            "warehouse_name": wh_name,
            "short_name": short_name(wh_name),
            "total_assigned": total_assigned,
            "total_success": total_success,
            "gtc_ratio": gtc_ratio
        })
    result.sort(key=lambda x: x["gtc_ratio"], reverse=True)
    return result


def parse_delayed_orders(z, sheet_targets, strings):
    """Parse delayed orders (>3 days) data."""
    if "4. Đơn >3D" not in sheet_targets:
        return []

    rows = fast_parse_sheet(z, sheet_targets["4. Đơn >3D"], strings)
    result = []
    for row in rows[3:]:
        if not row or len(row) < 5:
            continue
        wh_val = row[1]
        if wh_val is not None:
            wh_str = str(wh_val).lower()
            if "kho giao hàng nặng" in wh_str and any(kw in wh_str for kw in HANOI_KEYWORDS_LOWER):
                total_3d = float(row[2]) if row[2] is not None else 0.0
                over_7d = float(row[3]) if row[3] is not None else 0.0
                result.append({
                    "warehouse": str(wh_val),
                    "short_name": short_name(str(wh_val)),
                    "total_3d": total_3d,
                    "over_7d": over_7d
                })
    result.sort(key=lambda x: x["total_3d"], reverse=True)
    return result


def parse_overall_gtc(z, sheet_targets, strings):
    """Parse overall GTC from Backlog sheet."""
    if "1. Backlog" not in sheet_targets:
        return 0.0

    rows = fast_parse_sheet(z, sheet_targets["1. Backlog"], strings)
    for row in rows:
        if len(row) > 10 and row[8] == "GXT-HNO":
            try:
                return float(row[10]) * 100 if row[10] is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
    return 0.0


def parse_b2b_summary(z, sheet_targets, strings):
    """Parse B2B priority orders with breakdown by warehouse AND client/brand."""
    if "6.2 B2B | Đơn ƯU TIÊN GIAO" not in sheet_targets:
        return {"total": 0, "warehouses": [], "by_warehouse_client": {}}

    rows = fast_parse_sheet(z, sheet_targets["6.2 B2B | Đơn ƯU TIÊN GIAO"], strings)
    warehouse_counts = {}
    # Nested: { warehouse_short_name: { client_name: count } }
    wh_client = {}

    for row in rows[3:]:
        if not row or len(row) < 3:
            continue
        wh_val = str(row[2]) if row[2] is not None else ""
        client = str(row[5]) if len(row) > 5 and row[5] is not None else "Khác"
        wh_lower = wh_val.lower()
        if any(kw in wh_lower for kw in HANOI_KEYWORDS_LOWER):
            warehouse_counts[wh_val] = warehouse_counts.get(wh_val, 0) + 1
            sn = short_name(wh_val)
            if sn not in wh_client:
                wh_client[sn] = {}
            wh_client[sn][client] = wh_client[sn].get(client, 0) + 1

    total = sum(warehouse_counts.values())
    warehouses = sorted(
        [{"warehouse": k, "short_name": short_name(k), "count": v}
         for k, v in warehouse_counts.items()],
        key=lambda x: x["count"], reverse=True
    )

    # Sort clients within each warehouse by count desc
    for wh in wh_client:
        wh_client[wh] = dict(sorted(wh_client[wh].items(), key=lambda x: x[1], reverse=True))

    # Global client totals
    client_totals = {}
    for wh_data in wh_client.values():
        for client, count in wh_data.items():
            client_totals[client] = client_totals.get(client, 0) + count
    client_totals = dict(sorted(client_totals.items(), key=lambda x: x[1], reverse=True))

    return {
        "total": total,
        "warehouses": warehouses,
        "by_warehouse_client": wh_client,
        "client_totals": client_totals
    }

