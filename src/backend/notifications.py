# backend/notifications.py
import requests
from .config import Config

def send_order_notification(order_data, source):
    """Send order notification to Telegram Group"""
    items_text = "\n".join([f"   • {i['name']} x{i.get('quantity',1)} = <b>${i['price']*i.get('quantity',1):.2f}</b>" 
                           for i in order_data.get('items', [])])
    
    source_icon = "📱" if source == "QR Code" else "🤖"
    order_type_text = "Dine In" if order_data.get('order_type') == 'dine_in' else "Takeaway"
    table_info = f"\n<b>Table:</b> {order_data['table_number']}" if order_data.get('table_number') else ""
    
    message = f"""
<b>🆕 NEW ORDER RECEIVED!</b>
{source_icon} <b>Source:</b> {source}
━━━━━━━━━━━━━━━━━━━━
<b>Order #:</b> <code>{order_data.get('order_number')}</code>
<b>Customer:</b> {order_data.get('customer_name')}
<b>Phone:</b> {order_data.get('customer_phone')}
<b>Type:</b> {order_type_text}{table_info}

<b>Items:</b>
{items_text}
<b>Total:</b> <b>${order_data.get('total_amount', 0):.2f}</b>
━━━━━━━━━━━━━━━━━━━━
🔔 Please prepare the order! 🙏
"""
    
    try:
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': Config.GROUP_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        response = requests.post(url, data=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False

def send_ready_notification(order_num, customer_name, table_number):
    """Send ready notification to group"""
    message = f"""
<b>✅ ORDER READY FOR PICKUP!</b>
━━━━━━━━━━━━━━━━━━━━
<b>Order #:</b> <code>{order_num}</code>
<b>Customer:</b> {customer_name}
<b>Table:</b> {table_number or '📦 Takeaway'}

🎉 Food is ready! Please come and get it! 🍜
"""
    try:
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': Config.GROUP_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        requests.post(url, data=payload, timeout=5)
        return True
    except:
        return False