"""
Cron Job 15h — Báo cáo GTC ca sáng + cảnh báo
Chạy lúc 15:00 VN (08:00 UTC) mỗi ngày.

Logic:
1. Tải Google Sheet → parse GTC data
2. Tính %GTC theo kho cho ca sáng
3. Gửi báo cáo cho Quản lý
4. Nếu %GTC < 65% → Nhắc nhở NVPTTT + Warning Lead
"""
from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime, timezone, timedelta

from api.sheet_data import load_workbook, parse_gtc_data, parse_overall_gtc
from api.telegram_bot import send_to_manager, send_to_role, format_number, format_percent
from api.auth_middleware import send_json

CRON_SECRET = os.environ.get('CRON_SECRET', '')
GTC_THRESHOLD = float(os.environ.get('GTC_THRESHOLD', '65'))
VN_TZ = timezone(timedelta(hours=7))


def build_report_15h(gtc_data, overall_gtc):
    """Build the 15h afternoon GTC report."""
    now = datetime.now(VN_TZ)
    date_str = now.strftime('%d/%m/%Y')

    total_assigned = sum(w["total_assigned"] for w in gtc_data)
    total_success = sum(w["total_success"] for w in gtc_data)
    region_ratio = (total_success / total_assigned * 100) if total_assigned > 0 else 0

    lines = [
        f"📊 <b>BÁO CÁO GTC CA SÁNG — 15H</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📅 {date_str}",
        ""
    ]

    warnings = []

    for wh in gtc_data:
        ratio = wh["gtc_ratio"]
        if ratio >= GTC_THRESHOLD:
            status = "✅"
        else:
            status = "❌"
            warnings.append(wh)

        lines.append(f"🏭 <b>{wh['short_name']}</b>")
        lines.append(f"  Đơn gán: {format_number(wh['total_assigned'])} | GTC: {format_number(wh['total_success'])} | %GTC: {format_percent(ratio)} {status}")

        if ratio < GTC_THRESHOLD:
            lines.append(f"  → Dưới ngưỡng {format_percent(GTC_THRESHOLD)}")
        lines.append("")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"<b>Tổng vùng</b>: {format_number(total_assigned)} đơn | GTC: {format_number(total_success)} | %GTC: {format_percent(region_ratio)}")

    if overall_gtc > 0:
        lines.append(f"GTC tổng thể (Backlog): {format_percent(overall_gtc)}")

    return "\n".join(lines), warnings


def build_warning_lead(wh):
    """Build warning message for Lead of a specific warehouse."""
    now = datetime.now(VN_TZ)
    return (
        f"🚨 <b>CẢNH BÁO GTC THẤP — CA SÁNG</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 {now.strftime('%d/%m/%Y')}\n\n"
        f"Kho <b>{wh['short_name']}</b>: {format_percent(wh['gtc_ratio'])} (&lt; {format_percent(GTC_THRESHOLD)})\n\n"
        f"Đơn gán: {format_number(wh['total_assigned'])}\n"
        f"GTC: {format_number(wh['total_success'])}\n\n"
        f"→ Vui lòng kiểm tra và báo cáo nguyên nhân."
    )


def build_reminder_nvpttt(wh):
    """Build reminder message for NVPTTT of a specific warehouse."""
    return (
        f"⚠️ <b>NHẮC NHỞ — {wh['short_name']}</b>\n\n"
        f"%GTC ca sáng: <b>{format_percent(wh['gtc_ratio'])}</b> — thấp hơn mục tiêu {format_percent(GTC_THRESHOLD)}\n\n"
        f"Vui lòng đẩy mạnh giao hàng ca chiều."
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
            overall_gtc = parse_overall_gtc(z, sheet_targets, strings)

            # Build & send report to manager
            report, warnings = build_report_15h(gtc_data, overall_gtc)
            send_to_manager(report)

            # Send targeted alerts for low-GTC warehouses
            for wh in warnings:
                # Warning to Lead
                lead_msg = build_warning_lead(wh)
                send_to_role(wh["short_name"], "lead", lead_msg)

                # Reminder to NVPTTT
                nvpttt_msg = build_reminder_nvpttt(wh)
                send_to_role(wh["short_name"], "nvpttt", nvpttt_msg)

            # Summary warning to manager if any
            if warnings:
                summary = (
                    f"⚠️ <b>TÓM TẮT CẢNH BÁO 15H</b>\n\n"
                    f"{len(warnings)} kho có %GTC &lt; {format_percent(GTC_THRESHOLD)}:\n"
                )
                for wh in warnings:
                    summary += f"• {wh['short_name']}: {format_percent(wh['gtc_ratio'])}\n"
                summary += f"\nĐã gửi nhắc nhở cho Lead + NVPTTT."
                send_to_manager(summary)

            send_json(self, 200, {
                "ok": True,
                "report": "15h",
                "warehouses": len(gtc_data),
                "warnings": len(warnings)
            })

        except Exception as e:
            print(f"[Cron 15h] Error: {e}")
            send_json(self, 500, {"error": "Không thể tạo báo cáo 15h."})
