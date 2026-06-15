"""
Script lấy Chat ID từ Telegram Bot.
Chạy: python3 get_chat_id.py YOUR_BOT_TOKEN
"""
import sys
import urllib.request
import json

if len(sys.argv) < 2:
    print("Cách dùng: python3 get_chat_id.py YOUR_BOT_TOKEN")
    print("Ví dụ: python3 get_chat_id.py 7123456789:AAH-xxxxx")
    sys.exit(1)

token = sys.argv[1]
url = f"https://api.telegram.org/bot{token}/getUpdates"

try:
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read().decode('utf-8'))

    if not data.get('ok') or not data.get('result'):
        print("❌ Không tìm thấy tin nhắn nào.")
        print("   → Hãy gửi 1 tin nhắn vào nhóm có bot rồi chạy lại.")
        sys.exit(1)

    print("=" * 50)
    print("📱 DANH SÁCH CHAT/NHÓM TÌM THẤY:")
    print("=" * 50)

    seen = set()
    for update in data['result']:
        msg = update.get('message', {})
        chat = msg.get('chat', {})
        chat_id = chat.get('id')
        chat_type = chat.get('type', '')
        title = chat.get('title', chat.get('first_name', 'N/A'))

        if chat_id and chat_id not in seen:
            seen.add(chat_id)
            icon = "👥" if "group" in chat_type else "👤"
            print(f"\n{icon} {title}")
            print(f"   Chat ID: {chat_id}")
            print(f"   Loại: {chat_type}")

    print("\n" + "=" * 50)
    print("📋 HƯỚNG DẪN TIẾP THEO:")
    print("=" * 50)
    print("1. Copy Chat ID của nhóm (số âm, vd: -1001234567890)")
    print("2. Thêm vào Vercel Environment Variables:")
    print("   TELEGRAM_MANAGER_CHAT_ID = <chat_id>")
    print("3. Thêm vào GitHub Secrets:")
    print("   CRON_SECRET = <cùng giá trị trên Vercel>")

except Exception as e:
    print(f"❌ Lỗi: {e}")
    sys.exit(1)
