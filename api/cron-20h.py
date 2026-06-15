"""
Cron Job 20h — Tổng kết ngày + ghi nhận ca %GTC thấp
Chạy lúc 20:00 VN (13:00 UTC) mỗi ngày.

Logic:
1. Tải Google Sheet → parse ALL metrics
2. Tổng hợp: tổng đơn, GTC cả ngày, đơn tồn, B2B
3. Ghi nhận kho có %GTC thấp
4. Gửi báo cáo tổng kết cho Quản lý + Lead
"""
from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime, timezone, timedelta

from api.sheet_data import (
    load_workbook, parse_gtc_data, parse_delayed_orders,
    parse_b2b_summary, parse_overall_gtc
)
from api.telegram_bot import send_to_manager, send_to_role, format_number, format_percent
from api.auth_middleware import send_json

CRON_SECRET = os.environ.get('CRON_SECRET', '')
GTC_THRESHOLD = float(os.environ.get('GTC_THRESHOLD', '65'))
GTC_TARGET = float(os.environ.get('GTC_TARGET', '75'))
VN_TZ = timezone(timedelta(hours=7))


def build_report_20h(gtc_data, delayed_data, b2b_summary, overall_gtc):
    """Build the 20h end-of-day summary report."""
    now = datetime.now(VN_TZ)
    date_str = now.strftime('%d/%m/%Y')

    total_assigned = sum(w["total_assigned"] for w in gtc_data)
    total_success = sum(w["total_success"] for w in gtc_data)
    region_ratio = (total_success / total_assigned * 100) if total_assigned > 0 else 0

    target_status = "✅" if region_ratio >= GTC_TARGET else "⚠️"

    lines = [
        f"🌙 <b>TỔNG KẾT NGÀY — GHN HÀ NỘI</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📅 {date_str}",
        "",
        f"📈 <b>HIỆU SUẤT TOÀN VÙNG</b>",
        f"  Tổng đơn gán: {format_number(total_assigned)}",
        f"  GTC: {format_number(total_success)} ({format_percent(region_ratio)}) {target_status}",
        f"  Mục tiêu: {format_percent(GTC_TARGET)}",
    ]

    if overall_gtc > 0:
        lines.append(f"  GTC tổng thể (Backlog): {format_percent(overall_gtc)}")
    lines.append("")

    # Detailed table
    lines.append(f"📊 <b>CHI TIẾT THEO KHO</b>")
    lines.append(f"<pre>")
    lines.append(f"{'Kho':<16} {'Gán':>5} {'GTC':>5} {'%GTC':>7}")
    lines.append(f"{'─'*16} {'─'*5} {'─'*5} {'─'*7}")

    low_gtc_warehouses = []
    for wh in gtc_data:
        name = wh["short_name"][:16]
        assigned = int(wh["total_assigned"])
        success = int(wh["total_success"])
        ratio = wh["gtc_ratio"]
        flag = " ❌" if ratio < GTC_THRESHOLD else ""
        lines.append(f"{name:<16} {assigned:>5} {success:>5} {format_percent(ratio):>6}{flag}")

        if ratio < GTC_THRESHOLD:
            low_gtc_warehouses.append(wh)

    lines.append(f"</pre>")
    lines.append("")

    # Low GTC warehouses
    if low_gtc_warehouses:
        lines.append(f"⚠️ <b>KHO CẦN LƯU Ý</b>")
        for wh in low_gtc_warehouses:
            lines.append(f"  • <b>{wh['short_name']}</b>: {format_percent(wh['gtc_ratio'])} — dưới ngưỡng {format_percent(GTC_THRESHOLD)}")
        lines.append("")

    # Delayed orders
    total_delayed = sum(d["total_3d"] for d in delayed_data)
    total_over_7d = sum(d["over_7d"] for d in delayed_data)
    if total_delayed > 0:
        lines.append(f"📋 Đơn tồn >3 ngày: <b>{format_number(total_delayed)}</b> đơn (>7 ngày: {format_number(total_over_7d)})")

    # B2B detailed
    if b2b_summary["total"] > 0:
        lines.append(f"")
        lines.append(f"📦 <b>ĐƠN TỒN B2B ƯU TIÊN</b>: {b2b_summary['total']} đơn")

        # Client totals
        if b2b_summary.get("client_totals"):
            client_parts = []
            for client, count in b2b_summary["client_totals"].items():
                client_parts.append(f"{client}: {count}")
            lines.append(f"  Theo loại: {' | '.join(client_parts)}")

        # Per warehouse breakdown
        wh_client = b2b_summary.get("by_warehouse_client", {})
        for bw in b2b_summary["warehouses"]:
            sn = bw["short_name"]
            lines.append(f"  🏭 {sn}: {bw['count']} đơn")
            if sn in wh_client:
                for client, count in wh_client[sn].items():
                    lines.append(f"      • {client}: {count}")

    return "\n".join(lines), low_gtc_warehouses


def build_lead_eod_notice(wh):
    """Build end-of-day notice for Lead of low-GTC warehouse."""
    now = datetime.now(VN_TZ)
    return (
        f"📋 <b>GHI NHẬN KẾT QUẢ — {now.strftime('%d/%m/%Y')}</b>\n\n"
        f"Kho <b>{wh['short_name']}</b>\n"
        f"%GTC cả ngày: <b>{format_percent(wh['gtc_ratio'])}</b> ❌\n"
        f"Ngưỡng yêu cầu: {format_percent(GTC_THRESHOLD)}\n\n"
        f"Đã ghi nhận. Vui lòng chuẩn bị báo cáo nguyên nhân."
    )


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Verify cron secret
        if CRON_SECRET:
            auth = self.headers.get('Authorization', '')
            if auth != f'Bearer {CRON_SECRET}':
                send_json(self, 401, {"error": "Unauthorized"})
                return

        try:
            z, strings, sheet_targets = load_workbook()

            gtc_data = parse_gtc_data(z, sheet_targets, strings)
            delayed_data = parse_delayed_orders(z, sheet_targets, strings)
            b2b_summary = parse_b2b_summary(z, sheet_targets, strings)
            overall_gtc = parse_overall_gtc(z, sheet_targets, strings)

            # Build & send end-of-day report
            report, low_gtc = build_report_20h(gtc_data, delayed_data, b2b_summary, overall_gtc)
            send_to_manager(report)

            # Send EOD notices to Leads of low-GTC warehouses
            for wh in low_gtc:
                lead_msg = build_lead_eod_notice(wh)
                send_to_role(wh["short_name"], "lead", lead_msg)

            send_json(self, 200, {
                "ok": True,
                "report": "20h",
                "warehouses": len(gtc_data),
                "low_gtc": len(low_gtc)
            })

        except Exception as e:
            print(f"[Cron 20h] Error: {e}")
            send_json(self, 500, {"error": "Không thể tạo báo cáo 20h."})
