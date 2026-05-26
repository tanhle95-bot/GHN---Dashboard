from http.server import BaseHTTPRequestHandler
import json
import pandas as pd
import urllib.request
import io
import warnings

warnings.filterwarnings("ignore")

URL = "https://docs.google.com/spreadsheets/d/1Kjqwt6MIghCzfCSifVrpIpVHbC0o77lxMVVFlCZ26xY/export?format=xlsx"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
            response = urllib.request.urlopen(req)
            excel_data = io.BytesIO(response.read())
            
            data = {
                "gtc_ratio": [],
                "delayed_orders": [],
                "b2b_orders": [],
                "installation_orders": {
                    "success": [],
                    "pending": [],
                    "discrepancy": []
                }
            }
            
            # 1. GTC Ratio
            df_hieusuat = pd.read_excel(excel_data, sheet_name="raw_hieusuat")
            hanoi_hieusuat = df_hieusuat[df_hieusuat["warehouse_name"].astype(str).str.contains("Kho Giao Hàng Nặng", na=False)]
            hanoi_hieusuat = hanoi_hieusuat[hanoi_hieusuat["warehouse_name"].astype(str).str.contains("Hà Nội|HNO|Long Biên|Bắc Từ Liêm|Thanh Oai|Hoài Đức|Đức Long|Thanh Trì|Đông Anh", na=False)]
            
            gtc_summary = hanoi_hieusuat.groupby("warehouse_name").agg(
                total_assigned=("sld", "sum"),
                total_success=("sld_gtc", "sum")
            ).reset_index()
            gtc_summary["gtc_ratio"] = (gtc_summary["total_success"] / gtc_summary["total_assigned"]) * 100
            gtc_summary = gtc_summary.sort_values(by="gtc_ratio", ascending=False)
            data["gtc_ratio"] = gtc_summary.fillna(0).to_dict(orient="records")
            
            # 2. Delayed Orders > 3D
            df_3d = pd.read_excel(excel_data, sheet_name="4. Đơn >3D")
            col_wh = df_3d.columns[1]
            df_delayed = df_3d[[col_wh, df_3d.columns[2], df_3d.columns[3], df_3d.columns[4]]].copy()
            df_delayed = df_delayed[df_delayed[col_wh].astype(str).str.contains("Kho Giao Hàng Nặng.*Hà Nội|Kho Giao Hàng Nặng - Long Biên|Kho Giao Hàng Nặng - Bắc Từ Liêm|Kho Giao Hàng Nặng - Thanh Oai|Kho Giao Hàng Nặng - Hoài Đức|Kho Giao Hàng Nặng - Đức Long|Kho Giao Hàng Nặng - Thanh Trì|Kho Giao Hàng Nặng - Đông Anh", case=False, na=False)]
            df_delayed.columns = ["warehouse", "total_3d", "over_7d", "4_to_7d"]
            for col in ["total_3d", "over_7d", "4_to_7d"]:
                df_delayed[col] = pd.to_numeric(df_delayed[col], errors="coerce").fillna(0)
                
            def get_status(row):
                if row["over_7d"] >= 10 or row["total_3d"] >= 100:
                    return "Cảnh báo"
                elif row["over_7d"] > 0 or row["total_3d"] >= 20:
                    return "Cần lưu ý"
                else:
                    return "Bình thường"
                    
            df_delayed["status"] = df_delayed.apply(get_status, axis=1)
            df_delayed = df_delayed.sort_values(by="total_3d", ascending=False)
            data["delayed_orders"] = df_delayed.to_dict(orient="records")
            
            # 3. B2B Priority Orders
            df_b2b = pd.read_excel(excel_data, sheet_name="6.2 B2B | Đơn ƯU TIÊN GIAO")
            col_priority = df_b2b.columns[0]
            col_wh_b2b = df_b2b.columns[2]
            
            mask_b2b = pd.Series([False] * len(df_b2b))
            for col in df_b2b.columns:
                if df_b2b[col].dtype == object:
                    mask_b2b = mask_b2b | df_b2b[col].astype(str).str.contains("Hà Nội|HNO|Long Biên|Bắc Từ Liêm|Thanh Oai|Hoài Đức|Đức Long|Thanh Trì|Đông Anh", case=False, na=False)
                    
            hanoi_b2b = df_b2b[mask_b2b]
            b2b_summary = hanoi_b2b.groupby([col_wh_b2b, col_priority]).size().reset_index(name="count")
            
            pivot_b2b = b2b_summary.pivot(index=col_wh_b2b, columns=col_priority, values="count").fillna(0).reset_index()
            pivot_b2b.columns = ["warehouse"] + list(pivot_b2b.columns[1:])
            data["b2b_orders"] = pivot_b2b.to_dict(orient="records")
            
            # 4. Installation Orders
            df_install = pd.read_excel(excel_data, sheet_name="5. DS đơn Lắp đặt")
            df_install_hanoi = df_install[df_install["Kho hiện tại"].astype(str).str.contains("Hà Nội|HNO", na=False)]
            
            for _, row in df_install_hanoi.iterrows():
                item = {
                    "order_code": str(row["Mã đơn hàng"]),
                    "warehouse": str(row["Kho hiện tại"]),
                    "status": str(row["Trạng thái đơn hàng"]),
                    "install_type": str(row["Type lắp đặt"])
                }
                if row["Type lắp đặt"] == "Đã lắp đặt":
                    data["installation_orders"]["success"].append(item)
                elif row["Buyer đồng ý lắp đặt?"] == "Đồng ý" and row["Type lắp đặt"] != "Đã lắp đặt":
                    if row["Type lắp đặt"] == "Không cần lắp đặt":
                        data["installation_orders"]["discrepancy"].append(item)
                    else:
                        data["installation_orders"]["pending"].append(item)
                        
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            error_data = {"error": str(e)}
            self.wfile.write(json.dumps(error_data).encode('utf-8'))
