"""
Cron Job 10h — Báo cáo hàng mới về + tồn cũ + gán chuyến
Chạy lúc 10:00 VN (03:00 UTC) mỗi ngày.

Logic:
1. Tải Google Sheet
2. Tính: đơn tồn >3 ngày, GTC ratio theo kho (proxy cho gán chuyến)
3. Gửi báo cáo cho Quản lý
4. Nếu tỷ lệ thấp → Warning AM
"""
from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime, timezone, timedelta

from api.sheet_data import load_workbook, fast_parse_sheet, parse_gtc_data, parse_delayed_orders, parse_b2b_summary
from api.telegram_bot import send_to_manager, send_to_role, format_number, format_percent
from api.auth_middleware import send_json

CRON_SECRET = os.environ.get('CRON_SECRET', '')
ASSIGNMENT_THRESHOLD = float(os.environ.get('ASSIGNMENT_THRESHOLD', '70'))
VN_TZ = timezone(timedelta(hours=7))


def build_report_10h(gtc_data, delayed_data, b2b_summary):
    """Build the 10h morning report message."""
    now = datetime.now(VN_TZ)
    date_str = now.strftime('%d/%m/%Y')

    lines = [
        f"📦 <b>BÁO CÁO 10H — GHN HÀ NỘI</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📅 {date_str}",
        ""
    ]

    # GTC / Assignment by warehouse
    total_assigned = 0
    total_success = 0
    warnings = []

    for wh in gtc_data:
        total_assigned += wh["total_assigned"]
        total_success += wh["total_success"]
        ratio = wh["gtc_ratio"]

        status = "✅" if ratio >= ASSIGNMENT_THRESHOLD else "⚠️"
        lines.append(f"🏭 <b>{wh['short_name']}</b>")
        lines.append(f"  Đơn gán: {format_number(wh['total_assigned'])}")
        lines.append(f"  GTC: {format_number(wh['total_success'])} ({format_percent(ratio)}) {status}")

        if ratio < ASSIGNMENT_THRESHOLD:
            lines.append(f"  → Dưới ngưỡng {format_percent(ASSIGNMENT_THRESHOLD)}")
            warnings.append(wh)
        lines.append("")

    # Delayed orders summary
    total_delayed = sum(d["total_3d"] for d in delayed_data)
    total_over_7d = sum(d["over_7d"] for d in delayed_data)

    if delayed_data:
        lines.append(f"📋 <b>ĐƠN TỒN KHO</b>")
        lines.append(f"  Tồn >3 ngày: {format_number(total_delayed)} đơn")
        lines.append(f"  Tồn >7 ngày: {format_number(total_over_7d)} đơn")
        if delayed_data[:3]:
            lines.append(f"  Top kho tồn:")
            for d in delayed_data[:3]:
                lines.append(f"    • {d['short_name']}: {format_number(d['total_3d'])} đơn")
        lines.append("")

    # B2B detailed summary by warehouse + client
    if b2b_summary["total"] > 0:
        lines.append(f"📦 <b>ĐƠN TỒN B2B ƯU TIÊN</b>: {b2b_summary['total']} đơn")

        # Client totals
        if b2b_summary.get("client_totals"):
            client_parts = []
            for client, count in b2b_summary["client_totals"].items():
                client_parts.append(f"{client}: {count}")
            lines.append(f"  Theo loại: {' | '.join(client_parts)}")
        lines.append("")

        # Per warehouse breakdown
        wh_client = b2b_summary.get("by_warehouse_client", {})
        for bw in b2b_summary["warehouses"]:
            sn = bw["short_name"]
            lines.append(f"  🏭 <b>{sn}</b>: {bw['count']} đơn")
            if sn in wh_client:
                for client, count in wh_client[sn].items():
                    lines.append(f"      • {client}: {count}")
        lines.append("")

    # Overall
    overall_ratio = (total_success / total_assigned * 100) if total_assigned > 0 else 0
    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"Tổng: {format_number(total_assigned)} đơn gán | GTC: {format_number(total_success)} ({format_percent(overall_ratio)})")

    return "\n".join(lines), warnings


def build_warning_am(warnings):
    """Build warning message for AM."""
    now = datetime.now(VN_TZ)
    lines = [
        f"⚠️ <b>CẢNH BÁO GÁN CHUYẾN THẤP — 10H</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📅 {now.strftime('%d/%m/%Y')}",
        ""
    ]
    for wh in warnings:
        lines.append(f"• <b>{wh['short_name']}</b>: {format_percent(wh['gtc_ratio'])} (ngưỡng: {format_percent(ASSIGNMENT_THRESHOLD)})")
    lines.append("")
    lines.append("→ Cần kiểm tra và xử lý ngay.")
    return "\n".join(lines)


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

            # Build & send report
            report, warnings = build_report_10h(gtc_data, delayed_data, b2b_summary)
            send_to_manager(report)

            # Send warnings to AMs
            if warnings:
                warning_msg = build_warning_am(warnings)
                for wh in warnings:
                    send_to_role(wh["short_name"], "am", warning_msg)
                # Also send warning summary to manager
                send_to_manager(warning_msg)

            send_json(self, 200, {
                "ok": True,
                "report": "10h",
                "warehouses": len(gtc_data),
                "warnings": len(warnings)
            })

        except Exception as e:
            print(f"[Cron 10h] Error: {e}")
            send_json(self, 500, {"error": "Không thể tạo báo cáo 10h."})
