from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import io
import zipfile
import xml.etree.ElementTree as ET
from api.auth_middleware import check_auth, send_unauthorized, send_json

ALLOWED_SHEET_ID = os.environ.get('ALLOWED_SHEET_ID', '1Kjqwt6MIghCzfCSifVrpIpVHbC0o77lxMVVFlCZ26xY')
URL = f"https://docs.google.com/spreadsheets/d/{ALLOWED_SHEET_ID}/export?format=xlsx"


def fast_parse_sheet(z, sheet_file, strings):
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


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Authentication check
        username = check_auth(self)
        if not username:
            send_unauthorized(self)
            return

        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
            response = urllib.request.urlopen(req)
            excel_bytes = io.BytesIO(response.read())
            z = zipfile.ZipFile(excel_bytes)

            strings = []
            try:
                sst_xml = z.read("xl/sharedStrings.xml")
                root_sst = ET.fromstring(sst_xml)
                ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for t in root_sst.findall(".//ns:t", ns):
                    strings.append(t.text)
            except KeyError:
                pass

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

            # Parse B2B sheet
            result = {"total": 0, "by_client": {}, "by_warehouse": [], "orders": []}

            sheet_name = "6.2 B2B | Đơn ƯU TIÊN GIAO"
            if sheet_name in sheet_targets:
                rows_b2b = fast_parse_sheet(z, sheet_targets[sheet_name], strings)

                orders = []
                client_counts = {}
                warehouse_counts = {}

                for row in rows_b2b[3:]:
                    if not row or len(row) < 3:
                        continue

                    priority = str(row[0]) if row[0] is not None else ""
                    pic = str(row[1]) if len(row) > 1 and row[1] is not None else ""
                    warehouse = str(row[2]) if row[2] is not None else ""
                    order_code = str(row[3]) if len(row) > 3 and row[3] is not None else ""
                    action = str(row[4]) if len(row) > 4 and row[4] is not None else ""
                    client = str(row[5]) if len(row) > 5 and row[5] is not None else ""
                    address = str(row[6]) if len(row) > 6 and row[6] is not None else ""
                    inbound_date = str(row[7]) if len(row) > 7 and row[7] is not None else ""
                    storage_days = str(row[8]) if len(row) > 8 and row[8] is not None else "0"

                    if not order_code:
                        continue

                    orders.append({
                        "priority": priority,
                        "warehouse": warehouse,
                        "pic": pic,
                        "order_code": order_code,
                        "action": action,
                        "client": client,
                        "address": address,
                        "storage_days": storage_days
                    })

                    # Count by client
                    if client:
                        client_counts[client] = client_counts.get(client, 0) + 1
                    # Count by warehouse
                    if warehouse:
                        warehouse_counts[warehouse] = warehouse_counts.get(warehouse, 0) + 1

                result["total"] = len(orders)
                result["by_client"] = client_counts
                result["by_warehouse"] = sorted(
                    [{"warehouse": k, "count": v} for k, v in warehouse_counts.items()],
                    key=lambda x: x["count"],
                    reverse=True
                )
                result["orders"] = orders

            send_json(self, 200, result)

        except Exception:
            send_json(self, 500, {"error": "Không thể tải dữ liệu B2B. Vui lòng thử lại sau."})
