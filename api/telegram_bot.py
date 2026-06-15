"""
Telegram Bot helper — sends messages via Telegram Bot API.
Uses only urllib (no pip install needed for Vercel Python runtime).
"""
import os
import json
import urllib.request
import urllib.error
import urllib.parse

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
MANAGER_CHAT_ID = os.environ.get('TELEGRAM_MANAGER_CHAT_ID', '')

# TELEGRAM_CONTACTS format (JSON in env var):
# {
#   "Long Biên": {"lead": "chat_id", "nvpttt": "chat_id", "am": "chat_id"},
#   "Bắc Từ Liêm": {"lead": "chat_id", "nvpttt": "chat_id", "am": "chat_id"},
#   ...
# }
CONTACTS_RAW = os.environ.get('TELEGRAM_CONTACTS', '{}')

def get_contacts():
    """Parse contacts from env var."""
    try:
        return json.loads(CONTACTS_RAW)
    except (json.JSONDecodeError, TypeError):
        return {}


def send_message(chat_id, text, parse_mode='HTML'):
    """Send a message via Telegram Bot API. Returns True on success."""
    if not BOT_TOKEN or not chat_id:
        print(f"[Telegram] Skipping send — missing token or chat_id")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = json.dumps({
        'chat_id': str(chat_id),
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }).encode('utf-8')

    req = urllib.request.Request(
        url, data=data,
        headers={'Content-Type': 'application/json'}
    )

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode('utf-8'))
        return result.get('ok', False)
    except urllib.error.HTTPError as e:
        print(f"[Telegram] HTTP Error {e.code}: {e.read().decode('utf-8', errors='replace')}")
        return False
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


def send_to_manager(text, parse_mode='HTML'):
    """Send message to the manager (you)."""
    return send_message(MANAGER_CHAT_ID, text, parse_mode)


def send_to_role(warehouse_short_name, role, text, parse_mode='HTML'):
    """
    Send message to a specific role for a warehouse.
    role: 'lead', 'nvpttt', 'am'
    warehouse_short_name: e.g. 'Long Biên', 'Bắc Từ Liêm'
    """
    contacts = get_contacts()

    # Try exact match first, then partial match
    chat_id = None
    if warehouse_short_name in contacts:
        chat_id = contacts[warehouse_short_name].get(role)
    else:
        for wh_key, roles in contacts.items():
            if wh_key in warehouse_short_name or warehouse_short_name in wh_key:
                chat_id = roles.get(role)
                break

    if chat_id:
        return send_message(chat_id, text, parse_mode)
    else:
        print(f"[Telegram] No {role} contact found for warehouse: {warehouse_short_name}")
        return False


def format_number(n):
    """Format number with Vietnamese locale (comma as thousands separator)."""
    if isinstance(n, float):
        if n == int(n):
            return f"{int(n):,}".replace(",", ".")
        return f"{n:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(n):,}".replace(",", ".")


def format_percent(n):
    """Format percentage."""
    return f"{n:.1f}%"
