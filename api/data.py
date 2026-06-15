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
            # 1. Tải file Excel XLSX 11MB về bộ nhớ
            req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
            response = urllib.request.urlopen(req)
            excel_bytes = io.BytesIO(response.read())
            
            # 2. Giải nén nhanh zip XLSX
            z = zipfile.ZipFile(excel_bytes)
            
            # 3. Tải danh sách chuỗi dùng chung (sharedStrings.xml)
            strings = []
            try:
                sst_xml = z.read("xl/sharedStrings.xml")
                root_sst = ET.fromstring(sst_xml)
                ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for t in root_sst.findall(".//ns:t", ns):
                    strings.append(t.text)
            except KeyError:
                pass
                
            # 4. Ánh xạ các sheet name sang file XML tương ứng
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
            
            data = {
                "overall_gtc": 0.0,
                "gtc_ratio": [],
                "delayed_orders": [],
                "b2b_orders": [],
                "installation_orders": {
                    "success": [],
                    "pending": [],
                    "discrepancy": []
                }
            }
            
            # 1. GTC Ratio (Sheet: raw_hieusuat)
            if "raw_hieusuat" in sheet_targets:
                rows_hieusuat = fast_parse_sheet(z, sheet_targets["raw_hieusuat"], strings)
                header = rows_hieusuat[0]
                col_wh = header.index("warehouse_name")
                col_sld = header.index("sld")
                col_sld_gtc = header.index("sld_gtc")
                
                hanoi_keywords = ["Hà Nội", "HNO", "Long Biên", "Bắc Từ Liêm", "Thanh Oai", "Hoài Đức", "Đức Long", "Thanh Trì", "Đông Anh"]
                
                groups = {}
                for row in rows_hieusuat[1:]:
                    if not row or len(row) <= max(col_wh, col_sld, col_sld_gtc):
                        continue
                    wh_val = str(row[col_wh]) if row[col_wh] is not None else ""
                    if "Kho Giao Hàng Nặng" in wh_val and any(kw in wh_val for kw in hanoi_keywords):
                        sld_val = float(row[col_sld]) if row[col_sld] is not None else 0.0
                        sld_gtc_val = float(row[col_sld_gtc]) if row[col_sld_gtc] is not None else 0.0
                        
                        if wh_val not in groups:
                            groups[wh_val] = {"total_assigned": 0.0, "total_success": 0.0}
                        groups[wh_val]["total_assigned"] += sld_val
                        groups[wh_val]["total_success"] += sld_gtc_val
                
                gtc_ratio_list = []
                for wh_name, vals in groups.items():
                    total_assigned = vals["total_assigned"]
                    total_success = vals["total_success"]
                    gtc_ratio = (total_success / total_assigned * 100) if total_assigned > 0 else 0.0
                    gtc_ratio_list.append({
                        "warehouse_name": wh_name,
                        "total_assigned": total_assigned,
                        "total_success": total_success,
                        "gtc_ratio": gtc_ratio
                    })
                
                gtc_ratio_list.sort(key=lambda x: x["gtc_ratio"], reverse=True)
                data["gtc_ratio"] = gtc_ratio_list
            
            # 2. Đơn hoãn giao >3D (Sheet: 4. Đơn >3D)
            if "4. Đơn >3D" in sheet_targets:
                rows_delayed = fast_parse_sheet(z, sheet_targets["4. Đơn >3D"], strings)
                
                delayed_keywords = ["hà nội", "hno", "long biên", "bắc từ liêm", "thanh oai", "hoài đức", "đức long", "thanh trì", "đông anh"]
                
                delayed_list = []
                for row in rows_delayed[3:]: # Bỏ qua 2 hàng Note và hàng Header
                    if not row or len(row) < 5:
                        continue
                    wh_val = row[1]
                    if wh_val is not None:
                        wh_str = str(wh_val).lower()
                        if "kho giao hàng nặng" in wh_str and any(kw in wh_str for kw in delayed_keywords):
                            total_3d = float(row[2]) if row[2] is not None else 0.0
                            over_7d = float(row[3]) if row[3] is not None else 0.0
                            four_to_seven = float(row[4]) if row[4] is not None else 0.0
                            
                            if over_7d >= 10 or total_3d >= 100:
                                status = "Cảnh báo"
                            elif over_7d > 0 or total_3d >= 20:
                                status = "Cần lưu ý"
                            else:
                                status = "Bình thường"
                                
                            delayed_list.append({
                                "warehouse": str(wh_val),
                                "total_3d": total_3d,
                                "over_7d": over_7d,
                                "4_to_7d": four_to_seven,
                                "status": status
                            })
                
                delayed_list.sort(key=lambda x: x["total_3d"], reverse=True)
                data["delayed_orders"] = delayed_list
            
            # 3. Đơn B2B Ưu tiên (Sheet: 6.2 B2B | Đơn ƯU TIÊN GIAO)
            if "6.2 B2B | Đơn ƯU TIÊN GIAO" in sheet_targets:
                rows_b2b = fast_parse_sheet(z, sheet_targets["6.2 B2B | Đơn ƯU TIÊN GIAO"], strings)
                
                b2b_groups = {}
                priorities_set = set()
                hanoi_keywords_b2b = ["hà nội", "hno", "long biên", "bắc từ liêm", "thanh oai", "hoài đức", "đức long", "thanh trì", "đông anh"]
                
                for row in rows_b2b[3:]: # Bỏ qua 2 hàng Note và hàng Header
                    if not row or len(row) < 3:
                        continue
                    
                    wh_val = str(row[2]) if row[2] is not None else ""
                    wh_lower = wh_val.lower()
                    if any(kw in wh_lower for kw in hanoi_keywords_b2b):
                        priority_val = str(row[0]) if row[0] is not None else "Không xác định"
                        
                        priorities_set.add(priority_val)
                        if wh_val not in b2b_groups:
                            b2b_groups[wh_val] = {}
                        if priority_val not in b2b_groups[wh_val]:
                            b2b_groups[wh_val][priority_val] = 0
                        b2b_groups[wh_val][priority_val] += 1
                
                b2b_orders_list = []
                for wh_name, prio_counts in b2b_groups.items():
                    record = {"warehouse": wh_name}
                    for prio in priorities_set:
                        record[prio] = prio_counts.get(prio, 0)
                    b2b_orders_list.append(record)
                
                data["b2b_orders"] = b2b_orders_list
            
            # 4. Đơn lắp đặt (Sheet: 5. DS đơn Lắp đặt)
            if "5. DS đơn Lắp đặt" in sheet_targets:
                rows_inst = fast_parse_sheet(z, sheet_targets["5. DS đơn Lắp đặt"], strings)
                header = rows_inst[0]
                
                col_wh_inst = header.index("Kho hiện tại")
                col_code_inst = header.index("Mã đơn hàng")
                col_status_inst = header.index("Trạng thái đơn hàng")
                col_type_inst = header.index("Type lắp đặt")
                col_buyer_inst = header.index("Buyer đồng ý lắp đặt?")
                col_prov_inst = header.index("Tỉnh giao")
                col_prod_inst = header.index("Loại sản phẩm")
                
                for row in rows_inst[1:]:
                    if not row or len(row) <= max(col_wh_inst, col_code_inst, col_status_inst, col_type_inst, col_buyer_inst, col_prov_inst, col_prod_inst):
                        continue
                    wh_val = str(row[col_wh_inst]) if row[col_wh_inst] is not None else ""
                    if "Hà Nội" in wh_val or "HNO" in wh_val or "Đông Anh" in wh_val:
                        type_inst = str(row[col_type_inst]) if row[col_type_inst] is not None else ""
                        buyer_inst = str(row[col_buyer_inst]) if row[col_buyer_inst] is not None else ""
                        
                        item = {
                            "order_code": str(row[col_code_inst]) if row[col_code_inst] is not None else "",
                            "warehouse": wh_val,
                            "status": str(row[col_status_inst]) if row[col_status_inst] is not None else "",
                            "install_type": type_inst,
                            "buyer_agreed": buyer_inst,
                            "province": str(row[col_prov_inst]) if row[col_prov_inst] is not None else "",
                            "product_type": str(row[col_prod_inst]) if row[col_prod_inst] is not None else ""
                        }
                        
                        if type_inst == "Đã lắp đặt":
                            data["installation_orders"]["success"].append(item)
                        elif buyer_inst == "Đồng ý" and type_inst != "Đã lắp đặt":
                            if type_inst == "Không cần lắp đặt":
                                data["installation_orders"]["discrepancy"].append(item)
                            else:
                                data["installation_orders"]["pending"].append(item)
            
            # 5. Tỉ lệ GTC Tổng hợp Hà Nội (GXT-HNO) (Sheet: 1. Backlog)
            if "1. Backlog" in sheet_targets:
                rows_backlog = fast_parse_sheet(z, sheet_targets["1. Backlog"], strings)
                for row in rows_backlog:
                    if len(row) > 10 and row[8] == "GXT-HNO":
                        data["overall_gtc"] = float(row[10]) * 100 if row[10] is not None else 0.0
                        break
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
            
        except Exception:
            send_json(self, 500, {"error": "Không thể tải dữ liệu. Vui lòng thử lại sau."})
