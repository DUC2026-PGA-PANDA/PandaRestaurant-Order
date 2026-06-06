# backend/telegram_bot.py - Complete working version
import requests
import time
import threading
import json
import random
from datetime import datetime
from .config import Config
from .database import db_query, get_menu_items

# ==================== DATABASE FUNCTIONS ====================
def create_telegram_order(order_data, telegram_id):
    """Create order from Telegram"""
    order_num = f"PD{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}"
    total = sum(i['price'] * i.get('quantity', 1) for i in order_data.get('items', []))
    
    db_query('''INSERT INTO orders (order_number, customer_name, customer_phone, table_number, order_type, items, total_amount, notes, telegram_id, created_at, status) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
             (order_num, order_data.get('customer_name'), order_data.get('customer_phone'), 
              order_data.get('table_number'), order_data.get('order_type', 'dine_in'),
              json.dumps(order_data.get('items', [])), total, order_data.get('notes', ''), 
              telegram_id, datetime.now().isoformat(), 'pending'))
    # Notify admin dashboard (SSE) via backend push endpoint
    try:
        push_url = f"{Config.BASE_URL.rstrip('/')}/api/admin/push-order"
        payload = {
            'order_number': order_num,
            'customer_name': order_data.get('customer_name'),
            'customer_phone': order_data.get('customer_phone'),
            'table_number': order_data.get('table_number'),
            'order_type': order_data.get('order_type', 'takeaway'),
            'items': order_data.get('items', []),
            'total_amount': total,
            'created_at': datetime.now().isoformat(),
            'source': 'Telegram'
        }
        requests.post(push_url, json=payload, timeout=2)
    except Exception:
        pass
    return order_num, total

def get_user_cart(user_id):
    cart = db_query("SELECT cart FROM user_carts WHERE user_id = ?", (user_id,), fetch_one=True)
    if cart and cart['cart']:
        return json.loads(cart['cart'])
    return []

def save_user_cart(user_id, cart):
    db_query("INSERT OR REPLACE INTO user_carts (user_id, cart, updated_at) VALUES (?, ?, ?)",
             (user_id, json.dumps(cart), datetime.now().isoformat()))

def clear_user_cart(user_id):
    db_query("DELETE FROM user_carts WHERE user_id = ?", (user_id,))

def save_user_step(user_id, step, data=None):
    db_query("INSERT OR REPLACE INTO user_steps (user_id, step, step_data, updated_at) VALUES (?, ?, ?, ?)",
             (user_id, step, json.dumps(data) if data else None, datetime.now().isoformat()))

def get_user_step(user_id):
    return db_query("SELECT step, step_data FROM user_steps WHERE user_id = ?", (user_id,), fetch_one=True)

def clear_user_step(user_id):
    db_query("DELETE FROM user_steps WHERE user_id = ?", (user_id,))

# ==================== SEND MESSAGES ====================
def send_message(chat_id, text, keyboard=None, reply_keyboard=None):
    """Send message to Telegram.
    - `keyboard` is an InlineKeyboardMarkup dict (inline keyboard attached to the message).
    - `reply_keyboard` is a ReplyKeyboardMarkup dict (persistent keyboard shown under the input field).
    Only one `reply_markup` may be attached to a single message, so when both are provided
    `keyboard` (inline) takes precedence. To set both, call this function twice.
    """
    try:
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if keyboard:
            payload['reply_markup'] = json.dumps(keyboard)
        elif reply_keyboard:
            payload['reply_markup'] = json.dumps(reply_keyboard)
        requests.post(url, data=payload, timeout=5)
        return True
    except:
        return False

def edit_message(chat_id, message_id, text, keyboard=None):
    try:
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/editMessageText"
        payload = {'chat_id': chat_id, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML'}
        if keyboard:
            payload['reply_markup'] = json.dumps(keyboard)
        requests.post(url, data=payload, timeout=5)
    except:
        pass

def answer_callback(callback_id, text=None):
    try:
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/answerCallbackQuery"
        payload = {'callback_query_id': callback_id}
        if text:
            payload['text'] = text
        requests.post(url, data=payload, timeout=5)
    except:
        pass

# ==================== NOTIFICATIONS ====================
def send_order_to_group(order_num, order_data, total, source):
    """Send order to Telegram Group"""
    items_text = "\n".join([f"   • {i['name']} x{i.get('quantity',1)} = <b>${i['price']*i.get('quantity',1):.2f}</b>" 
                           for i in order_data.get('items', [])])
    
    source_icon = "🤖" if source == "Telegram Bot" else "📱"
    order_type_text = "Dine In" if order_data.get('order_type') == 'dine_in' else "Takeaway"
    table_info = f"\n<b>Table:</b> {order_data['table_number']}" if order_data.get('table_number') else ""
    
    message = f"""
<b>🆕 NEW ORDER!</b>
{source_icon} <b>Source:</b> {source}
━━━━━━━━━━━━━━━━━━━━
<b>Order #:</b> <code>{order_num}</code>
<b>Customer:</b> {order_data.get('customer_name')}
<b>Phone:</b> {order_data.get('customer_phone')}
<b>Type:</b> {order_type_text}{table_info}

<b>Items:</b>
{items_text}
<b>Total:</b> <b>${total:.2f}</b>
━━━━━━━━━━━━━━━━━━━━
🔔 Please prepare! 🙏"""
    
    try:
        url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': Config.GROUP_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        response = requests.post(url, data=payload, timeout=5)
        if response.status_code == 200:
            print(f"✅ Order #{order_num} sent to group")
            return True
        print(f"⚠️ Group notification failed ({response.status_code}): {response.text}")
        return False
    except Exception as e:
        print(f"Error sending to group: {e}")
        return False

def send_order_confirmation(chat_id, order_num, order_data, total):
    """Send confirmation to customer"""
    items_list = "\n".join([f"• {i['name']} x{i['quantity']} = ${i['price']*i['quantity']:.2f}" for i in order_data.get('items', [])])
    order_type_text = "Dine In" if order_data.get('order_type') == 'dine_in' else "Takeaway"
    table_info = f"\n<b>Table:</b> {order_data['table_number']}" if order_data.get('table_number') else ""
    
    message = f"""
✅ <b>ORDER CONFIRMED!</b>
━━━━━━━━━━━━━━━━━━━━
<b>Order #:</b> <code>{order_num}</code>
<b>Name:</b> {order_data.get('customer_name')}
<b>Phone:</b> {order_data.get('customer_phone')}
<b>Type:</b> {order_type_text}{table_info}

<b>Items:</b>
{items_list}

<b>Total:</b> <b>${total:.2f}</b>
━━━━━━━━━━━━━━━━━━━━
⏱️ <b>Estimated time:</b> 15-20 minutes

Thank you for ordering from Panda Restaurant! 🍜
"""
    send_message(chat_id, message)

# ==================== KEYBOARDS ====================
def get_main_keyboard():
    return {
        'inline_keyboard': [
            [
                {'text': '🍜 Noodles', 'callback_data': 'cat_khmer_noodles'},
                {'text': '🥤 Drinks', 'callback_data': 'cat_drinks'}
            ],
            [
                {'text': '🍲 Main Dishes', 'callback_data': 'cat_main_dishes'},
                {'text': '🍚 Rice Dishes', 'callback_data': 'cat_rice_dishes'}
            ],
            [
                {'text': '🍰 Desserts', 'callback_data': 'cat_desserts'}
            ],
            [{'text': '🍜 View Menu', 'callback_data': 'view_menu'}],
            [{'text': '🛒 My Cart', 'callback_data': 'view_cart'}],
            [{'text': '📋 My Orders', 'callback_data': 'my_orders'}],
            [
                {'text': '❓ Help', 'callback_data': 'help'},
                {'text': '🔥 Today\'s Specials', 'callback_data': 'todays_specials'}
            ]
        ]
    }

def get_category_keyboard():
    categories = [
        {'key': 'khmer_noodles', 'name': '🍜 Noodles'},
        {'key': 'drinks', 'name': '🥤 Drinks'},
        {'key': 'main_dishes', 'name': '🍲 Main Dishes'},
        {'key': 'rice_dishes', 'name': '🍚 Rice Dishes'},
        {'key': 'desserts', 'name': '🍰 Desserts'}
    ]
    keyboard = [[{'text': cat['name'], 'callback_data': f"cat_{cat['key']}"}] for cat in categories]
    keyboard.append([{'text': '🔙 Back to Main', 'callback_data': 'main_menu'}])
    return {'inline_keyboard': keyboard}

def get_cart_keyboard():
    return {
        'inline_keyboard': [
            [{'text': '✅ Checkout', 'callback_data': 'checkout'}],
            [{'text': '💳 Pay Now', 'callback_data': 'pay_now'}],
            [{'text': '🗑️ Clear Cart', 'callback_data': 'clear_cart'}],
            [{'text': '🔙 Continue Shopping', 'callback_data': 'view_menu'}]
        ]
    }

def get_reply_keyboard():
    """Persistent reply keyboard shown below the input field (single 'Menu' button)."""
    # Return None to disable the persistent reply keyboard (remove 'Menu' button)
    return None

def get_order_type_keyboard():
    return {
        'inline_keyboard': [
            [{'text': '🏠 Dine In', 'callback_data': 'order_type_dine'}],
            [{'text': '📦 Takeaway', 'callback_data': 'order_type_takeaway'}]
        ]
    }

# ==================== ORDER PROCESSING ====================
def process_checkout(chat_id, message_id, user_id):
    cart = get_user_cart(user_id)
    if not cart:
        text = "❌ Your cart is empty! Add items before checkout."
        keyboard = {'inline_keyboard': [[{'text': '🍜 Browse Menu', 'callback_data': 'view_menu'}]]}
        edit_message(chat_id, message_id, text, keyboard)
        return
    
    # default: not requiring immediate payment
    save_user_step(user_id, 'awaiting_order_type', {'cart': cart, 'require_payment': False})
    text = "✅ <b>Checkout</b>\n\nPlease select your order type:"
    edit_message(chat_id, message_id, text, get_order_type_keyboard())

def handle_pay_now(chat_id, message_id, user_id):
    cart = get_user_cart(user_id)
    if not cart:
        send_message(chat_id, "❌ Your cart is empty!")
        return
    # mark that we require payment after placing order
    save_user_step(user_id, 'awaiting_order_type', {'cart': cart, 'require_payment': True})
    edit_message(chat_id, message_id, "✅ <b>Checkout</b>\n\nPlease select your order type:", get_order_type_keyboard())

def process_order_type(chat_id, user_id, order_type):
    save_user_step(user_id, 'awaiting_name', {'order_type': order_type})
    send_message(chat_id, "👤 Please enter your <b>full name</b>:")

def process_name(chat_id, user_id, name):
    step = get_user_step(user_id)
    if not step:
        send_message(chat_id, "❌ Session expired. Please start over.")
        return
    
    data = json.loads(step['step_data']) if step['step_data'] else {}
    data['name'] = name
    save_user_step(user_id, 'awaiting_phone', data)
    send_message(chat_id, "📞 Please enter your <b>phone number</b>:")

def process_phone(chat_id, user_id, phone):
    step = get_user_step(user_id)
    if not step:
        send_message(chat_id, "❌ Session expired. Please start over.")
        return
    
    data = json.loads(step['step_data']) if step['step_data'] else {}
    order_type = data.get('order_type')
    name = data.get('name')
    
    if not order_type or not name:
        send_message(chat_id, "❌ Missing information. Please start over.")
        clear_user_step(user_id)
        return
    
    data['phone'] = phone
    
    if order_type == 'dine_in':
        save_user_step(user_id, 'awaiting_table', data)
        send_message(chat_id, "🏠 Please enter your <b>table number</b> (1-20):")
    else:
        complete_order(chat_id, user_id, data)

def process_table_number(chat_id, user_id, table_num):
    step = get_user_step(user_id)
    if not step:
        send_message(chat_id, "❌ Session expired. Please start over.")
        return
    
    data = json.loads(step['step_data']) if step['step_data'] else {}
    data['table_number'] = table_num
    complete_order(chat_id, user_id, data)

def complete_order(chat_id, user_id, data):
    order_type = data.get('order_type')
    name = data.get('name')
    phone = data.get('phone')
    table_num = data.get('table_number')
    
    # Get cart
    cart = get_user_cart(user_id)
    if not cart:
        send_message(chat_id, "❌ Your cart is empty!")
        clear_user_step(user_id)
        return
    
    # Calculate total
    total = sum(i['price'] * i['quantity'] for i in cart)
    
    # Prepare order items
    order_items = [{'name': i['name'], 'price': i['price'], 'quantity': i['quantity']} for i in cart]
    
    # Create order data
    order_data = {
        'customer_name': name,
        'customer_phone': phone,
        'items': order_items,
        'total_amount': total,
        'order_type': order_type
    }
    if table_num:
        order_data['table_number'] = table_num
    
    # Create order in database
    order_num, order_total = create_telegram_order(order_data, user_id)

    # Send confirmation to customer
    send_order_confirmation(chat_id, order_num, order_data, order_total)

    # Check if payment required
    step = get_user_step(user_id)
    require_payment = False
    if step and step['step_data']:
        sd = json.loads(step['step_data'])
        require_payment = sd.get('require_payment', False)

    if require_payment:
        # Create a Stripe Checkout session via backend and send payment link
        try:
            payload = {'order_number': order_num, 'items': order_items}
            create_url = f"{Config.BASE_URL.rstrip('/')}/create-checkout-session"
            resp = requests.post(create_url, json=payload, timeout=10)
            if resp.status_code == 200 and resp.json().get('url'):
                pay_url = resp.json()['url']
                keyboard = {'inline_keyboard': [[{'text': '💳 Pay Online', 'url': pay_url}], [{'text': '❌ Cancel', 'callback_data': f'cancel_payment_{order_num}'}]]}
                send_message(chat_id, f"💳 To pay for your order <code>{order_num}</code>, open the link below:", keyboard)
                save_user_step(user_id, 'awaiting_payment', {'order_number': order_num})
            else:
                error_msg = resp.json().get('error') if resp.headers.get('Content-Type', '').startswith('application/json') else None
                send_message(chat_id, f"❌ Failed to create payment link. {error_msg or 'Please try again later.'}")
        except Exception as e:
            print(f"Payment link failure: {e}")
            send_message(chat_id, "❌ Payment service unavailable. Please try again later.")
    else:
        # Send order to group
        success = send_order_to_group(order_num, order_data, order_total, "Telegram Bot")
        if not success:
            send_message(chat_id, "⚠️ Your order is confirmed, but the kitchen notification failed. We will retry automatically.")
        # Clean up
        clear_user_cart(user_id)
        clear_user_step(user_id)

# ==================== QUICK ORDER (one-step) ====================
def initiate_quick_order(chat_id, user_id, first_name, item_id, quantity=1):
    """Start a quick order for a single item; ask for phone to complete."""
    items = get_menu_items()
    item = next((i for i in items if i['id'] == item_id), None)
    if not item:
        send_message(chat_id, "❌ Item not found. Use /menu to browse items.")
        return

    name = item['name_kh'] if item['name_kh'] else item['name']
    order_items = [{'name': name, 'price': item['price'], 'quantity': quantity}]

    order_data = {
        'customer_name': first_name or 'Customer',
        'customer_phone': None,
        'items': order_items,
        'order_type': 'takeaway',
        'notes': ''
    }

    # save step waiting for phone to complete quick order
    save_user_step(user_id, 'awaiting_quick_phone', order_data)
    send_message(chat_id, f"📦 Quick order prepared for <b>{name}</b> x{quantity}.\nPlease enter your <b>phone number</b> to complete the order:")

def process_quick_phone(chat_id, user_id, phone):
    """Complete a quick order after receiving phone number."""
    step = get_user_step(user_id)
    if not step or step['step'] != 'awaiting_quick_phone':
        send_message(chat_id, "❌ No quick order in progress. Use /order_now <item_id> to start.")
        return

    data = json.loads(step['step_data']) if step['step_data'] else {}
    data['customer_phone'] = phone

    # create order from provided quick-order data
    order_items = data.get('items', [])
    total = sum(i['price'] * i.get('quantity', 1) for i in order_items)

    order_num, order_total = create_telegram_order(data, user_id)

    send_order_confirmation(chat_id, order_num, data, order_total)
    send_order_to_group(order_num, data, order_total, "Telegram Bot (Quick)")

    clear_user_step(user_id)

# ==================== MENU HANDLERS ====================
def send_welcome(chat_id, user_id, username, first_name):
    db_query("INSERT OR REPLACE INTO telegram_users (user_id, username, first_name, chat_id, last_interaction) VALUES (?, ?, ?, ?, ?)",
             (user_id, username, first_name, chat_id, datetime.now().isoformat()))
    
    text = f"""
🐼 <b>Welcome to Panda Restaurant, {first_name}!</b>

We serve authentic Cambodian noodles and delicious Khmer cuisine.

<b>📋 How to order:</b>
1. Click "View Menu" to browse dishes
2. Add items to your cart
3. Click "My Cart" to review
4. Click "Checkout" and select order type
5. Enter your name and phone number
6. Confirm your order

<b>🍜 Today's Special:</b>
• Nom Banh Chok Traditional - $4.50
• Beef Lok Lak - $5.50
• Mango Sticky Rice - $3.50
"""
    # Send welcome message and set persistent reply keyboard, then show inline main menu
    send_message(chat_id, text, reply_keyboard=get_reply_keyboard())
    send_message(chat_id, "🏠 Main Menu", get_main_keyboard())

def send_menu(chat_id, message_id=None):
    text = "📋 <b>Select a category:</b>"
    if message_id:
        edit_message(chat_id, message_id, text, get_category_keyboard())
    else:
        send_message(chat_id, text, get_category_keyboard())
        # ensure persistent reply keyboard is present
        send_message(chat_id, "Use the Menu button below to quickly open categories.", reply_keyboard=get_reply_keyboard())

def send_subcategories(chat_id, message_id, category):
    """Show available subcategories for a category, with an 'All' option."""
    rows = db_query("SELECT DISTINCT subcategory FROM menu_items WHERE category = ? AND available = 1", (category,), fetch_all=True)
    subs = [r['subcategory'] for r in rows] if rows else []
    if not subs:
        send_message(chat_id, "❌ No subcategories found.")
        return

    keyboard = {'inline_keyboard': []}
    for s in subs:
        keyboard['inline_keyboard'].append([{'text': s.title(), 'callback_data': f'subcat_{category}_{s}'}])
    keyboard['inline_keyboard'].append([{'text': '📋 Show All', 'callback_data': f'all_{category}'}])
    keyboard['inline_keyboard'].append([{'text': '🔙 Back', 'callback_data': 'view_menu'}])
    text = f"📂 <b>{category.replace('_', ' ').title()}</b>\n\nChoose a subcategory:" 
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

def send_specials(chat_id, message_id=None):
    """Show today's specials with quick-order and add-to-cart buttons."""
    # Define special names (these match menu item `name` or `name_kh` inserted in database)
    special_names = ['Nom Banh Chok Traditional', 'Beef Lok Lak', 'Mango Sticky Rice']
    items = get_menu_items()
    specials = [i for i in items if i['name'] in special_names or i['name_kh'] in special_names]

    if not specials:
        send_message(chat_id, "❌ No specials found right now.")
        return

    keyboard = {'inline_keyboard': []}
    for item in specials:
        name = item['name_kh'] if item['name_kh'] else item['name']
        keyboard['inline_keyboard'].append([
            {'text': f'🛒 Add {name} to Cart', 'callback_data': f'add_special_to_cart_{item["id"]}'},
            {'text': f'✅ Order {name} Now', 'callback_data': f'quick_order_{item["id"]}'}
        ])

    keyboard['inline_keyboard'].append([{'text': '🔙 Back to Main', 'callback_data': 'main_menu'}])
    text = "🔥 <b>Today's Specials</b>\n\nChoose an action:"
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)

def send_items_by_category(chat_id, message_id, category, subcategory=None):
    items = get_menu_items(category, subcategory)
    if not items:
        send_message(chat_id, "❌ No items found.")
        return
    
    keyboard = {'inline_keyboard': []}
    for item in items:
        name = item['name_kh'] if item['name_kh'] else item['name']
        keyboard['inline_keyboard'].append([{'text': f"💰 ${item['price']} - {name}", 'callback_data': f"item_{item['id']}"}])
    
    keyboard['inline_keyboard'].append([{'text': '🔙 Back', 'callback_data': 'view_menu'}])
    keyboard['inline_keyboard'].append([{'text': '🛒 View Cart', 'callback_data': 'view_cart'}])
    
    title = category.replace('_', ' ').title()
    if subcategory:
        title = f"{title} — {subcategory.title()}"
    edit_message(chat_id, message_id, f"🍽️ <b>{title}</b>", keyboard)

def send_item_detail(chat_id, message_id, item_id, user_id):
    items = get_menu_items()
    item = next((i for i in items if i['id'] == item_id), None)
    if not item:
        send_message(chat_id, "❌ Item not found.")
        return
    
    name = item['name_kh'] if item['name_kh'] else item['name']
    cart = get_user_cart(user_id)
    current_qty = next((i['quantity'] for i in cart if i['item_id'] == item_id), 0)
    
    text = f"""
🍽️ <b>{name}</b>
<i>{item['name']}</i>

💰 Price: ${item['price']}
⏱️ Prep time: {item['preparation_time']} min
📝 {item['description'] or 'Delicious dish'}

<b>In cart:</b> {current_qty}
"""
    
    keyboard = {
        'inline_keyboard': [
            [{'text': '➖', 'callback_data': f'qty_{item_id}_-1'}, {'text': '➕', 'callback_data': f'qty_{item_id}_1'}],
            [{'text': '✅ Add to Cart', 'callback_data': f'add_to_cart_{item_id}'}],
            [{'text': '🔙 Back', 'callback_data': f'cat_{item["category"]}'}]
        ]
    }
    edit_message(chat_id, message_id, text, keyboard)

def send_cart(chat_id, message_id, user_id):
    cart = get_user_cart(user_id)
    if not cart:
        text = "🛒 Your cart is empty!"
        keyboard = {'inline_keyboard': [[{'text': '🍜 Browse Menu', 'callback_data': 'view_menu'}]]}
        edit_message(chat_id, message_id, text, keyboard)
        return
    
    total = 0
    items_text = ""
    for i, item in enumerate(cart, 1):
        item_total = item['price'] * item['quantity']
        total += item_total
        items_text += f"{i}. {item['name']} x{item['quantity']} = ${item_total:.2f}\n"
    
    text = f"""
🛒 <b>Your Cart</b>

{items_text}
━━━━━━━━━━━━━━━━━━━━
<b>Total:</b> ${total:.2f}
"""
    edit_message(chat_id, message_id, text, get_cart_keyboard())

def send_my_orders(chat_id, user_id):
    orders = db_query("SELECT order_number, status, total_amount, created_at FROM orders WHERE telegram_id = ? ORDER BY created_at DESC LIMIT 10", (user_id,), fetch_all=True)
    
    if not orders:
        text = "📋 You haven't placed any orders yet."
        keyboard = {'inline_keyboard': [[{'text': '🍜 Start Ordering', 'callback_data': 'view_menu'}]]}
        send_message(chat_id, text, keyboard)
        return
    
    text = "📋 <b>My Recent Orders</b>\n\n"
    for order in orders:
        status_emoji = {'pending': '⏳', 'preparing': '🔥', 'ready': '✅', 'completed': '📦'}.get(order['status'], '❓')
        text += f"{status_emoji} <b>#{order['order_number']}</b>\n"
        text += f"   💰 ${order['total_amount']:.2f}\n"
        text += f"   📅 {order['created_at'][:10]}\n"
        text += f"   📍 Status: {order['status']}\n\n"
    
    keyboard = {'inline_keyboard': [[{'text': '🍜 New Order', 'callback_data': 'view_menu'}]]}
    send_message(chat_id, text, keyboard)

def send_help(chat_id):
    text = """
❓ <b>Help & Support</b>

<b>How to order:</b>
1. View Menu → Select items → Add to Cart
2. My Cart → Checkout
3. Select order type (Dine In / Takeaway)
4. Enter your name and phone
5. For Dine In, enter table number
6. Order confirmed!

<b>Commands:</b>
/start - Restart
/menu - Browse menu
/cart - View cart
/orders - My history
"""
    send_message(chat_id, text)

def add_to_cart(user_id, item_id):
    items = get_menu_items()
    item = next((i for i in items if i['id'] == item_id), None)
    if not item:
        return False
    
    cart = get_user_cart(user_id)
    name = item['name_kh'] if item['name_kh'] else item['name']
    existing = next((i for i in cart if i['item_id'] == item_id), None)
    
    if existing:
        existing['quantity'] += 1
    else:
        cart.append({'item_id': item_id, 'name': name, 'price': item['price'], 'quantity': 1})
    
    save_user_cart(user_id, cart)
    return True

def update_quantity(user_id, item_id, delta):
    cart = get_user_cart(user_id)
    existing = next((i for i in cart if i['item_id'] == item_id), None)
    if existing:
        existing['quantity'] += delta
        if existing['quantity'] <= 0:
            cart = [i for i in cart if i['item_id'] != item_id]
        save_user_cart(user_id, cart)
        return True
    return False

def clear_cart(user_id):
    clear_user_cart(user_id)

# ==================== MAIN BOT LOOP ====================
def run_telegram_bot():
    last_update_id = 0
    print(f"📱 Bot: https://t.me/{Config.BOT_USERNAME}")
    print("💡 Order flow: Select order type → Enter name → Enter phone → (Table for Dine In) → Complete")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/getUpdates"
            response = requests.get(url, params={'offset': last_update_id + 1, 'timeout': 30})
            updates = response.json()
            
            if updates.get('ok'):
                for update in updates.get('result', []):
                    last_update_id = update['update_id']
                    
                    # Callback queries
                    if 'callback_query' in update:
                        cb = update['callback_query']
                        chat_id = cb['message']['chat']['id']
                        msg_id = cb['message']['message_id']
                        data = cb['data']
                        user_id = str(cb['from']['id'])
                        
                        answer_callback(cb['id'])
                        
                        if data == 'main_menu':
                            send_message(chat_id, "🏠 Main Menu", get_main_keyboard())
                            # ensure persistent reply keyboard is present
                            send_message(chat_id, "Use the Menu button below to quickly open categories.", reply_keyboard=get_reply_keyboard())
                        elif data == 'view_menu':
                            send_menu(chat_id, msg_id)
                        elif data == 'todays_specials':
                            send_specials(chat_id, msg_id)
                        elif data.startswith('cat_'):
                            # show subcategories first
                            send_subcategories(chat_id, msg_id, data.replace('cat_', ''))
                        elif data.startswith('subcat_'):
                            parts = data.split('_', 2)
                            if len(parts) == 3:
                                cat = parts[1]
                                sub = parts[2]
                                send_items_by_category(chat_id, msg_id, cat, sub)
                        elif data.startswith('all_'):
                            cat = data.replace('all_', '')
                            send_items_by_category(chat_id, msg_id, cat)
                        elif data.startswith('item_'):
                            send_item_detail(chat_id, msg_id, int(data.replace('item_', '')), user_id)
                        elif data.startswith('qty_'):
                            parts = data.split('_')
                            update_quantity(user_id, int(parts[1]), int(parts[2]))
                            send_item_detail(chat_id, msg_id, int(parts[1]), user_id)
                        elif data.startswith('add_to_cart_'):
                            add_to_cart(user_id, int(data.replace('add_to_cart_', '')))
                            answer_callback(cb['id'], "✅ Added to cart!")
                            send_item_detail(chat_id, msg_id, int(data.replace('add_to_cart_', '')), user_id)
                        elif data == 'view_cart':
                            send_cart(chat_id, msg_id, user_id)
                        elif data == 'clear_cart':
                            clear_cart(user_id)
                            send_cart(chat_id, msg_id, user_id)
                        elif data == 'checkout':
                            process_checkout(chat_id, msg_id, user_id)
                        elif data == 'pay_now':
                            handle_pay_now(chat_id, msg_id, user_id)
                        elif data == 'order_type_dine':
                            process_order_type(chat_id, user_id, 'dine_in')
                        elif data == 'order_type_takeaway':
                            process_order_type(chat_id, user_id, 'takeaway')
                        elif data == 'my_orders':
                            send_my_orders(chat_id, user_id)
                        elif data == 'help':
                            send_help(chat_id)
                        elif data.startswith('quick_order_'):
                            try:
                                item_id = int(data.replace('quick_order_', ''))
                                user_first = cb['from'].get('first_name', '')
                                initiate_quick_order(chat_id, user_id, user_first, item_id, 1)
                            except:
                                answer_callback(cb['id'], '❌ Could not start quick order')
                        elif data.startswith('add_special_to_cart_'):
                            try:
                                item_id = int(data.replace('add_special_to_cart_', ''))
                                add_to_cart(user_id, item_id)
                                answer_callback(cb['id'], '✅ Added to cart')
                            except:
                                answer_callback(cb['id'], '❌ Could not add to cart')
                        elif data.startswith('confirm_payment_'):
                            order_no = data.replace('confirm_payment_', '')
                            # mark order as paid
                            db_query("UPDATE orders SET status = ? WHERE order_number = ?", ('paid', order_no))
                            send_message(chat_id, f"✅ Payment received for order <code>{order_no}</code>. We'll start preparing it.")
                            # fetch order to send to group
                            order_row = db_query("SELECT items, total_amount FROM orders WHERE order_number = ?", (order_no,), fetch_one=True)
                            try:
                                items = json.loads(order_row['items']) if order_row and order_row['items'] else []
                                total = order_row['total_amount'] if order_row else 0
                                send_order_to_group(order_no, {'items': items, 'customer_name': '', 'customer_phone': ''}, total, 'Telegram Bot (Paid)')
                            except:
                                pass
                            # clear user cart and steps
                            clear_user_cart(user_id)
                            clear_user_step(user_id)
                        elif data.startswith('cancel_payment_'):
                            order_no = data.replace('cancel_payment_', '')
                            db_query("UPDATE orders SET status = ? WHERE order_number = ?", ('cancelled', order_no))
                            send_message(chat_id, f"❌ Payment cancelled for order <code>{order_no}</code>.")
                            clear_user_step(user_id)
                    
                    # Text messages
                    elif 'message' in update:
                        msg = update['message']
                        chat_id = msg['chat']['id']
                        user_id = str(msg['from']['id'])
                        text = msg.get('text', '').strip()
                        username = msg['from'].get('username', '')
                        first_name = msg['from'].get('first_name', '')
                        
                        # Check for /start command FIRST so users can restart at any time
                        if text == '/start':
                            clear_user_step(user_id)
                            send_welcome(chat_id, user_id, username, first_name)
                        # Handle persistent Reply Keyboard 'Menu' button
                        elif text == 'Menu':
                            # user tapped the persistent Menu button — show categories
                            send_menu(chat_id)
                            send_message(chat_id, "Use the Menu button below to quickly open categories.", reply_keyboard=get_reply_keyboard())
                        else:
                            step = get_user_step(user_id)
                            
                            if step and step['step'] == 'awaiting_name':
                                process_name(chat_id, user_id, text)
                            elif step and step['step'] == 'awaiting_quick_phone':
                                process_quick_phone(chat_id, user_id, text)
                            elif step and step['step'] == 'awaiting_phone':
                                process_phone(chat_id, user_id, text)
                            elif step and step['step'] == 'awaiting_table':
                                try:
                                    table_num = int(text)
                                    if 1 <= table_num <= 20:
                                        process_table_number(chat_id, user_id, table_num)
                                    else:
                                        send_message(chat_id, "❌ Table number must be 1-20. Try again:")
                                except:
                                    send_message(chat_id, "❌ Please enter a valid number. Example: 5")
                            elif text.startswith('/'):
                                if text == '/menu':
                                    send_menu(chat_id)
                                    # set persistent reply keyboard for users using the command
                                    send_message(chat_id, "Use the Menu button below to quickly open categories.", reply_keyboard=get_reply_keyboard())
                                elif text.startswith('/order_now'):
                                    parts = text.split()
                                    if len(parts) >= 2:
                                        try:
                                            item_id = int(parts[1])
                                            qty = int(parts[2]) if len(parts) >= 3 else 1
                                            initiate_quick_order(chat_id, user_id, first_name, item_id, qty)
                                        except:
                                            send_message(chat_id, "❌ Usage: /order_now <item_id> [quantity]\nExample: /order_now 5 2")
                                    else:
                                        send_message(chat_id, "❌ Usage: /order_now <item_id> [quantity]\nExample: /order_now 5 2")
                                elif text == '/cart':
                                    cart = get_user_cart(user_id)
                                    if cart:
                                        total = sum(i['price'] * i['quantity'] for i in cart)
                                        items_text = "\n".join([f"• {i['name']} x{i['quantity']} = ${i['price']*i['quantity']:.2f}" for i in cart])
                                        send_message(chat_id, f"🛒 <b>Your Cart</b>\n\n{items_text}\n━━━━━━━━━━━━━━━━━━━━\n<b>Total:</b> ${total:.2f}", get_cart_keyboard())
                                    else:
                                        send_message(chat_id, "🛒 Your cart is empty! Use /menu to add items.")
                                elif text == '/orders':
                                    send_my_orders(chat_id, user_id)
                                else:
                                    send_message(chat_id, "❓ Unknown command. Use /start")
                            else:
                                # If no step and no command, just ignore
                                pass
            
            time.sleep(1)
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(5)

def start_bot_thread():
    thread = threading.Thread(target=run_telegram_bot, daemon=True)
    thread.start()
    return thread