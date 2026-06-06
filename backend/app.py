# backend/app.py - New complete version
from flask import Flask, request, jsonify, send_from_directory, redirect, Response, stream_with_context
from flask_cors import CORS
import qrcode
from io import BytesIO
import base64
import json
import random
import sqlite3
from datetime import datetime
import os
import traceback
import queue
try:
    import stripe
except Exception:
    stripe = None
import requests
from .config import Config

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# Simple in-memory pubsub for Server-Sent Events (SSE)
order_listeners = []

# ==================== DATABASE ====================
DB_PATH = Config.DATABASE_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, name_kh TEXT, category TEXT, price REAL,
            description TEXT, image_url TEXT, preparation_time INTEGER DEFAULT 10
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE, customer_name TEXT, customer_phone TEXT,
            table_number INTEGER, order_type TEXT, status TEXT DEFAULT 'pending',
            items TEXT, total_amount REAL, notes TEXT, created_at TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tables (table_number INTEGER PRIMARY KEY)
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_carts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            cart TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            step TEXT,
            step_data TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telegram_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            username TEXT,
            first_name TEXT,
            chat_id TEXT,
            last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM menu_items")
    if cursor.fetchone()[0] == 0:
        sample_items = [
            # ====== KHMER NOODLES (10+ items) ======
            ('Nom Banh Chok Traditional', 'នំបញ្ចុកប្រពៃណី', 'khmer_noodles', 4.50, 
             'Traditional Cambodian rice noodles', 'https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=300', 12),
            ('Nom Banh Chok Curry', 'នំបញ្ចុកសម្លការី', 'khmer_noodles', 5.00,
             'Rice noodles with curry sauce', 'https://images.unsplash.com/photo-1626664334295-9c0a5e6af2b3?w=300', 15),
            ('Nom Banh Chok Seafood', 'នំបញ្ចុកសមុទ្រ', 'khmer_noodles', 6.50,
             'Noodles with shrimp and squid', 'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=300', 15),
            ('Nom Banh Chok Beef', 'នំបញ្ចុកសាច់គោ', 'khmer_noodles', 6.00,
             'Noodles with grilled beef', 'https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=300', 15),
            ('Nom Banh Chok Chicken', 'នំបញ្ចុកសាច់មាន់', 'khmer_noodles', 5.50,
             'Noodles with grilled chicken', 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300', 12),
            ('Nom Banh Chok Vegetarian', 'នំបញ្ចុកបួរ', 'khmer_noodles', 4.50,
             'Vegetarian rice noodles', 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300', 10),
            ('Beef Stir-fried Noodles', 'គុយទាវឆាសាច់គោ', 'khmer_noodles', 5.50,
             'Stir-fried wide noodles with beef', 'https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=300', 10),
            ('Seafood Fried Noodles', 'មីឆាសមុទ្រ', 'khmer_noodles', 6.00,
             'Fried noodles with seafood', 'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=300', 10),
            ('Cambodian Noodle Soup', 'គុយទាវខ្មែរ', 'khmer_noodles', 4.50,
             'Traditional noodle soup with herbs', 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300', 10),
            ('Korean Ramen', 'មីកូរ៉េ', 'khmer_noodles', 6.50,
             'Spicy Korean ramen noodles', 'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=300', 12),
            
            # ====== DRINKS (10+ items) ======
            ('Iced Coffee Latte', 'កាហ្វេទឹកកក', 'drinks', 2.50,
             'Strong Cambodian iced coffee', 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=300', 5),
            ('Iced Milk Tea', 'តែទឹកដោះគោ', 'drinks', 2.00,
             'Creamy iced milk tea', 'https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=300', 5),
            ('Fresh Coconut Juice', 'ទឹកត្រកៀបស្រស់', 'drinks', 2.50,
             'Fresh coconut water from young coconut', 'https://images.unsplash.com/photo-1587049352846-4a222e784d38?w=300', 3),
            ('Fresh Lime Soda', 'ទឹកក្រូចក្តាម', 'drinks', 1.80,
             'Refreshing lime soda with mint', 'https://images.unsplash.com/photo-1505577058444-a3dab196a8b6?w=300', 2),
            ('Fresh Orange Juice', 'ទឹកក្រូចស្រស់', 'drinks', 1.50,
             'Fresh squeezed orange juice', 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=300', 3),
            ('Strawberry Smoothie', 'ក្រឡុកស្ត្របឺរី', 'drinks', 3.00,
             'Strawberry smoothie with yogurt', 'https://images.unsplash.com/photo-1553530667-cd8dffb67bca?w=300', 5),
            ('Mango Smoothie', 'ក្រឡុកស្វាយ', 'drinks', 3.00,
             'Fresh mango smoothie', 'https://images.unsplash.com/photo-1590556541000-c100d76ecc56?w=300', 5),
            ('Hot Green Tea', 'តែបៃតង', 'drinks', 1.50,
             'Green tea with honey', 'https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=300', 3),
            ('Coconut Smoothie', 'ទឹកដូងក្រឡុក', 'drinks', 3.00,
             'Coconut and banana smoothie', 'https://images.unsplash.com/photo-1590556541000-c100d76ecc56?w=300', 5),
            ('Hot Coffee', 'កាហ្វេក្តៅ', 'drinks', 2.00,
             'Hot Cambodian coffee', 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=300', 3),
            ('Passion Fruit Juice', 'ទឹកឆ្ងាញ់ក្ក', 'drinks', 2.50,
             'Fresh passion fruit juice', 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=300', 3),
            
            # ====== MAIN DISHES (10+ items) ======
            ('Fried Spring Rolls', 'ស៊ុបគ្រឿងចៀន', 'main_dishes', 3.00,
             'Crispy fried spring rolls', 'https://images.unsplash.com/photo-1582450871972-b5b9d4b2d7f1?w=300', 8),
            ('Fresh Spring Rolls', 'ស៊ុបគ្រឿងស្រស់', 'main_dishes', 3.50,
             'Fresh spring rolls with shrimp', 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300', 8),
            ('Green Mango Salad', 'ញាក់ស្វាយ', 'main_dishes', 4.00,
             'Spicy green mango salad', 'https://images.unsplash.com/photo-1607532941433-304659e8198a?w=300', 10),
            ('Papaya Salad', 'បុកល្ហុង', 'main_dishes', 4.00,
             'Traditional papaya salad with peanuts', 'https://images.unsplash.com/photo-1607532941433-304659e8198a?w=300', 10),
            ('Vegetable Stir Fry', 'បន្លែឆា', 'main_dishes', 3.50,
             'Mixed vegetables stir-fried', 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=300', 12),
            ('Chicken Satay', 'សាតេ', 'main_dishes', 4.50,
             'Grilled chicken skewers with peanut sauce', 'https://images.unsplash.com/photo-1599599810694-b5ac4dd5e1c9?w=300', 12),
            ('Shrimp Tempura', 'បង្គាក្រcapitoចូរ', 'main_dishes', 5.00,
             'Crispy fried shrimp', 'https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec?w=300', 10),
            ('Fish Cake', 'នំបុ័ងត្រី', 'main_dishes', 3.50,
             'Steamed fish cake with dipping sauce', 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300', 8),
            ('Beef Jerky', 'សាច់គោស្ងួត', 'main_dishes', 4.00,
             'Dried beef with chili', 'https://images.unsplash.com/photo-1599599810694-b5ac4dd5e1c9?w=300', 6),
            ('Chicken Wings', 'ស្លាបមាន់', 'main_dishes', 4.50,
             'Grilled chicken wings with sauce', 'https://images.unsplash.com/photo-1567521464027-f127ff144326?w=300', 12),
            
            # ====== RICE DISHES (10+ items) ======
            ('Beef Lok Lak', 'ឡុកឡាក់សាច់គោ', 'rice_dishes', 5.50,
             'Stir-fried beef with rice and lime', 'https://images.unsplash.com/photo-1600891964092-4316c288032e?w=300', 15),
            ('Chicken Lok Lak', 'ឡុកឡាក់មាន់', 'rice_dishes', 5.00,
             'Stir-fried chicken with rice', 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300', 12),
            ('Grilled Fish with Rice', 'ត្រីអាំងផាត', 'rice_dishes', 6.50,
             'Grilled fish served with steamed rice', 'https://images.unsplash.com/photo-1546069901-eacef0df6022?w=300', 18),
            ('Shrimp Fried Rice', 'បាយឆាបង្គា', 'rice_dishes', 5.50,
             'Fried rice with shrimp and vegetables', 'https://images.unsplash.com/photo-1609501676725-7186f017a4b5?w=300', 10),
            ('Chicken Fried Rice', 'បាយឆាមាន់', 'rice_dishes', 4.50,
             'Fried rice with chicken', 'https://images.unsplash.com/photo-1609501676725-7186f017a4b5?w=300', 10),
            ('Vegetable Fried Rice', 'បាយឆាបួរ', 'rice_dishes', 4.00,
             'Vegetarian fried rice', 'https://images.unsplash.com/photo-1609501676725-7186f017a4b5?w=300', 8),
            ('Beef Fried Rice', 'បាយឆាសាច់គោ', 'rice_dishes', 5.00,
             'Fried rice with beef and egg', 'https://images.unsplash.com/photo-1609501676725-7186f017a4b5?w=300', 10),
            ('Mixed Seafood Rice', 'បាយសមុទ្រ', 'rice_dishes', 7.00,
             'Rice with shrimp, squid and fish', 'https://images.unsplash.com/photo-1609501676725-7186f017a4b5?w=300', 15),
            ('Pork Chop Rice', 'ស្លាបមាន់ផាត', 'rice_dishes', 5.50,
             'Grilled pork chop with rice', 'https://images.unsplash.com/photo-1600891964092-4316c288032e?w=300', 15),
            ('Duck Roast Rice', 'ទាបង្គាក្រボង', 'rice_dishes', 6.50,
             'Roasted duck with rice and sauce', 'https://images.unsplash.com/photo-1600891964092-4316c288032e?w=300', 18),
            
            # ====== DESSERTS (10+ items) ======
            ('Mango Sticky Rice', 'ស្វាយដំណើប', 'desserts', 3.50,
             'Sweet mango with sticky rice', 'https://images.unsplash.com/photo-1605881527547-e7cf4c2a463e?w=300', 10),
            ('Coconut Pancake', 'នំបុ័ងដូង', 'desserts', 2.80,
             'Soft coconut pancakes with syrup', 'https://images.unsplash.com/photo-1523986371872-9d3ba2e2f642?w=300', 7),
            ('Fried Banana', 'ចេកចៀន', 'desserts', 2.50,
             'Crispy fried banana with honey', 'https://images.unsplash.com/photo-1563805042-7684c019e157?w=300', 8),
            ('Coconut Custard', 'សាលាដូង', 'desserts', 3.00,
             'Baked custard with coconut', 'https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=300', 12),
            ('Tapioca Pudding', 'នំស្ពាត់ដូង', 'desserts', 2.50,
             'Sweet tapioca with coconut milk', 'https://images.unsplash.com/photo-1563805042-7684c019e157?w=300', 8),
            ('Pandan Cake', 'នំប៉ាន់ដាន់', 'desserts', 3.00,
             'Green pandan flavored cake', 'https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=300', 10),
            ('Mango Pudding', 'ស្វាយលាយ', 'desserts', 3.00,
             'Smooth mango pudding', 'https://images.unsplash.com/photo-1563805042-7684c019e157?w=300', 8),
            ('Sweet Rice Cake', 'នំកុក', 'desserts', 2.50,
             'Traditional sweet rice cake', 'https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=300', 8),
            ('Sesame Ball', 'នំក្រ្ឯក', 'desserts', 2.00,
             'Fried sesame ball with filling', 'https://images.unsplash.com/photo-1563805042-7684c019e157?w=300', 6),
            ('Mango Sorbet', 'ស្វាយស្ម័ង', 'desserts', 3.50,
             'Refreshing mango ice sorbet', 'https://images.unsplash.com/photo-1563805042-7684c019e157?w=300', 5),
        ]
        for item in sample_items:
            cursor.execute('''INSERT INTO menu_items (name, name_kh, category, price, description, image_url, preparation_time) 
                VALUES (?,?,?,?,?,?,?)''', item)
    
    for i in range(1, 12):
        cursor.execute("INSERT OR IGNORE INTO tables (table_number) VALUES (?)", (i,))
    
    conn.commit()
    conn.close()
    print("✅ Database initialized!")

# Use centralized DB initialization from backend.database (ensures subcategory column)
try:
    from . import database as _db
    _db.init_database()
except Exception as e:
    print(f"DB init error: {e}")

def db_query(query, params=(), fetch_one=False, fetch_all=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    if fetch_one:
        result = cursor.fetchone()
    elif fetch_all:
        result = cursor.fetchall()
    else:
        result = cursor.lastrowid
        conn.commit()
    conn.close()
    return result

# ==================== NOTIFICATION FUNCTION ====================
def send_order_notification(order_data, source):
    """Send order notification to Telegram Group"""
    from .notifications import send_order_notification as send_notif
    send_notif(order_data, source)

def send_ready_notification(order_num, customer_name, table_number):
    """Send ready notification to group"""
    from .notifications import send_ready_notification as send_ready
    send_ready(order_num, customer_name, table_number)

# ==================== ROUTES ====================
@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/mobile-menu')
def mobile_menu():
    return send_from_directory('../frontend', 'menu.html')

@app.route('/table-menu/<int:table_num>')
def table_menu(table_num):
    return send_from_directory('../frontend', 'menu.html')

@app.route('/admin/login')
def admin_login():
    return send_from_directory('../frontend', 'admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    return send_from_directory('../frontend', 'admin.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('../frontend', path)

# ==================== API ROUTES ====================
@app.route('/api/categories')
def api_categories():
    categories = [
        {'key': 'khmer_noodles', 'name': '🍜 Noodles', 'icon': '🍜'},
        {'key': 'drinks', 'name': '🥤 Drinks', 'icon': '🥤'},
        {'key': 'main_dishes', 'name': '🍲 Main Dishes', 'icon': '🍲'},
        {'key': 'rice_dishes', 'name': '🍚 Rice Dishes', 'icon': '🍚'},
        {'key': 'desserts', 'name': '🍰 Desserts', 'icon': '🍰'}
    ]
    return jsonify(categories)

@app.route('/api/menu')
def api_menu():
    category = request.args.get('category')
    if category:
        items = db_query("SELECT * FROM menu_items WHERE category = ?", (category,), fetch_all=True)
    else:
        items = db_query("SELECT * FROM menu_items", fetch_all=True)
    return jsonify([dict(item) for item in items])

@app.route('/api/tables')
def api_tables():
    tables = db_query("SELECT table_number FROM tables ORDER BY table_number", fetch_all=True)
    result = []
    for t in tables:
        qr_url = f"http://192.168.3.144:5000/table-menu/{t['table_number']}"
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        result.append({
            'table_number': t['table_number'], 
            'qr_code': img_base64,
            'qr_url': qr_url
        })
    return jsonify(result)

@app.route('/api/table/<int:table_num>/qr')
def get_table_qr(table_num):
    qr_url = f"http://192.168.3.144:5000/table-menu/{table_num}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    return jsonify({'table_number': table_num, 'qr_code': img_base64})

@app.route('/api/table-order', methods=['POST'])
def api_table_order():
    """Handle web orders and send notifications"""
    data = request.get_json() or {}
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid request payload'}), 400
    if not isinstance(data.get('items'), list) or len(data.get('items')) == 0:
        return jsonify({'error': 'Order items are required'}), 400
    if not data.get('customer_name'):
        return jsonify({'error': 'Customer name is required'}), 400

    order_num = f"PD{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}"
    try:
        total = sum(i['price'] * i.get('quantity', 1) for i in data.get('items', []))
    except Exception:
        return jsonify({'error': 'Invalid item data'}), 400
    
    # Prepare order data for notification
    order_data = {
        'order_number': order_num,
        'customer_name': data.get('customer_name'),
        'customer_phone': data.get('customer_phone'),
        'table_number': data.get('table_number'),
        'order_type': data.get('order_type', 'dine_in'),
        'items': data.get('items', []),
        'total_amount': total,
        'notes': data.get('notes', '')
    }
    
    # Save to database
    db_query('''INSERT INTO orders (order_number, customer_name, customer_phone, table_number, order_type, items, total_amount, notes, created_at) 
                VALUES (?,?,?,?,?,?,?,?,?)''',
             (order_num, data.get('customer_name'), data.get('customer_phone'), 
              data.get('table_number'), data.get('order_type', 'dine_in'),
              json.dumps(data.get('items', [])), total, data.get('notes', ''), datetime.now().isoformat()))
    
    # Send notification to Telegram Group
    send_order_notification(order_data, "QR Code (Web)")
    
    return jsonify({'success': True, 'order_number': order_num})


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    data = request.get_json() or {}
    if stripe is None:
        return jsonify({'error': 'Stripe SDK not installed'}), 500
    if not Config.STRIPE_SECRET_KEY:
        return jsonify({'error': 'Stripe not configured'}), 400

    order_number = data.get('order_number')
    items = data.get('items')
    if not order_number or not isinstance(items, list) or len(items) == 0:
        return jsonify({'error': 'Invalid order data'}), 400

    stripe.api_key = Config.STRIPE_SECRET_KEY
    line_items = []
    try:
        for it in items:
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': it.get('name')},
                    'unit_amount': int(float(it.get('price', 0)) * 100)
                },
                'quantity': int(it.get('quantity', 1))
            })
    except Exception:
        return jsonify({'error': 'Invalid item pricing or quantity'}), 400

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=Config.STRIPE_SUCCESS_URL,
            cancel_url=Config.STRIPE_CANCEL_URL,
            metadata={'order_number': order_number}
        )
        return jsonify({'url': session.url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    if not Config.STRIPE_WEBHOOK_SECRET:
        return jsonify({'error': 'Webhook secret not configured'}), 400

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, Config.STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_no = session.get('metadata', {}).get('order_number')
        payment_intent = session.get('payment_intent')
        try:
            conn = sqlite3.connect(Config.DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("UPDATE orders SET payment_status = ?, stripe_payment_id = ?, status = ? WHERE order_number = ?", ('paid', payment_intent, 'paid', order_no))
            conn.commit()
            cur.execute("SELECT items, total_amount FROM orders WHERE order_number = ?", (order_no,))
            row = cur.fetchone()
            if row:
                items = json.loads(row[0]) if row[0] else []
                total = row[1]
                # try to clear user's cart/steps if telegram_id exists
                cur.execute("SELECT telegram_id FROM orders WHERE order_number = ?", (order_no,))
                tr = cur.fetchone()
                if tr and tr[0]:
                    try:
                        db_conn = sqlite3.connect(Config.DATABASE_PATH)
                        db_cur = db_conn.cursor()
                        db_cur.execute("DELETE FROM user_carts WHERE user_id = ?", (tr[0],))
                        db_cur.execute("DELETE FROM user_steps WHERE user_id = ?", (tr[0],))
                        db_conn.commit()
                        db_conn.close()
                    except:
                        pass
                try:
                    msg = f"<b>🆕 NEW PAID ORDER</b>\nOrder #: <code>{order_no}</code>\nTotal: ${total:.2f}"
                    url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
                    requests.post(url, data={'chat_id': Config.GROUP_CHAT_ID, 'text': msg, 'parse_mode': 'HTML'})
                except Exception:
                    pass
        except Exception as e:
            print('Webhook DB error:', e)
        finally:
            conn.close()

    return jsonify({'status': 'received'})

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    print('Unhandled exception:', traceback.format_exc())
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/admin/stream')
def api_admin_stream():
    def gen(q):
        try:
            while True:
                data = q.get()
                yield f"data: {json.dumps(data)}\n\n"
        except GeneratorExit:
            return

    q = queue.Queue()
    order_listeners.append(q)
    return Response(stream_with_context(gen(q)), mimetype='text/event-stream')


@app.route('/api/admin/push-order', methods=['POST'])
def api_admin_push_order():
    # Accepts order JSON and broadcasts to connected admin SSE listeners
    data = request.get_json() or {}
    if not isinstance(data, dict) or not data.get('order_number'):
        return jsonify({'error': 'Invalid order payload'}), 400
    for q in list(order_listeners):
        try:
            q.put(data, block=False)
        except Exception:
            pass
    return jsonify({'ok': True})

@app.route('/api/order/<order_num>/status', methods=['POST'])
def api_update_status(order_num):
    data = request.json
    new_status = data.get('status')
    db_query("UPDATE orders SET status = ? WHERE order_number = ?", (new_status, order_num))
    
    # Send notification when order is ready
    if new_status == 'ready':
        order = db_query("SELECT * FROM orders WHERE order_number = ?", (order_num,), fetch_one=True)
        if order:
            send_ready_notification(order_num, order['customer_name'], order['table_number'])
    
    return jsonify({'success': True})

@app.route('/api/stats')
def api_stats():
    today = datetime.now().strftime('%Y-%m-%d')
    orders = db_query("SELECT * FROM orders WHERE created_at LIKE ?", (f"{today}%",), fetch_all=True)
    return jsonify({'total_orders': len(orders)})

# ==================== ADMIN API ROUTES ====================
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
sessions = {}

@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    data = request.json
    if data.get('username') == ADMIN_USERNAME and data.get('password') == ADMIN_PASSWORD:
        import secrets
        token = secrets.token_hex(32)
        sessions[token] = datetime.now().isoformat()
        response = jsonify({'success': True})
        response.set_cookie('admin_session', token, httponly=True, max_age=3600*24)
        return response
    return jsonify({'success': False}), 401

@app.route('/api/admin/logout', methods=['POST'])
def api_admin_logout():
    token = request.cookies.get('admin_session')
    if token in sessions:
        del sessions[token]
    response = jsonify({'success': True})
    response.set_cookie('admin_session', '', expires=0)
    return response

def check_admin():
    token = request.cookies.get('admin_session')
    return token in sessions

@app.route('/api/admin/stats')
def api_admin_stats():
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    
    stats = db_query("""
        SELECT 
            COUNT(*) as total_orders,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'preparing' THEN 1 ELSE 0 END) as preparing,
            SUM(CASE WHEN status = 'ready' THEN 1 ELSE 0 END) as ready,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(total_amount) as total_revenue
        FROM orders WHERE date(created_at) = date('now')
    """, fetch_one=True)
    
    return jsonify({
        'total_orders': stats['total_orders'] or 0,
        'pending': stats['pending'] or 0,
        'preparing': stats['preparing'] or 0,
        'ready': stats['ready'] or 0,
        'completed': stats['completed'] or 0,
        'total_revenue': stats['total_revenue'] or 0
    })

@app.route('/api/admin/orders')
def api_admin_orders():
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    
    orders = db_query("""
        SELECT order_number, customer_name, customer_phone, table_number, 
               order_type, status, total_amount, notes, created_at
        FROM orders ORDER BY created_at DESC LIMIT 100
    """, fetch_all=True)
    return jsonify([dict(o) for o in orders])

@app.route('/api/admin/order/<order_num>/items')
def api_admin_order_items(order_num):
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    
    order = db_query("SELECT items FROM orders WHERE order_number = ?", (order_num,), fetch_one=True)
    if order and order['items']:
        items = json.loads(order['items'])
        return jsonify(items)
    return jsonify([])

@app.route('/api/admin/order/<order_num>/status', methods=['PUT'])
def api_admin_update_status(order_num):
    if not check_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    new_status = data.get('status')
    db_query("UPDATE orders SET status = ? WHERE order_number = ?", (new_status, order_num))
    
    # Send notification when ready
    if new_status == 'ready':
        order = db_query("SELECT * FROM orders WHERE order_number = ?", (order_num,), fetch_one=True)
        if order:
            send_ready_notification(order_num, order['customer_name'], order['table_number'])
    
    return jsonify({'success': True})

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🐼 PANDA RESTAURANT - Backend Server")
    print("="*60)
    print("📍 Local: http://localhost:5000")
    print("📍 Network: http://192.168.3.144:5000")
    print("🍜 Menu: http://192.168.3.144:5000/mobile-menu")
    print("👨‍💼 Admin Login: http://192.168.3.144:5000/admin/login")
    print("📋 Admin Credentials: admin / admin123")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)