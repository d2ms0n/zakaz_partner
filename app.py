from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Database initialization
def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    
    # Create tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_info TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            min_price DECIMAL(10,2) NOT NULL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id INTEGER,
            order_date DATE,
            total_amount DECIMAL(10,2),
            FOREIGN KEY (partner_id) REFERENCES partners (id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            price DECIMAL(10,2),
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # Insert sample data только если таблицы пустые
    c.execute("SELECT COUNT(*) FROM partners")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO partners (name, contact_info) VALUES ('Partner 1', 'contact1@email.com')")
        c.execute("INSERT INTO partners (name, contact_info) VALUES ('Partner 2', 'contact2@email.com')")
        c.execute("INSERT INTO partners (name, contact_info) VALUES ('Partner 3', 'contact3@email.com')")
        
        c.execute("INSERT INTO products (name, min_price) VALUES ('Product A', 100.50)")
        c.execute("INSERT INTO products (name, min_price) VALUES ('Product B', 200.75)")
        c.execute("INSERT INTO products (name, min_price) VALUES ('Product C', 150.00)")
        c.execute("INSERT INTO products (name, min_price) VALUES ('Product D', 300.25)")
    
    conn.commit()
    conn.close()

# Инициализируем базу при запуске
init_db()


# API Endpoints
@app.route('/api/partners', methods=['GET'])
def api_partners():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM partners")
    partners = c.fetchall()
    conn.close()
    
    partners_list = []
    for partner in partners:
        partners_list.append({
            'id': partner[0],
            'name': partner[1],
            'contact_info': partner[2]
        })
    
    return jsonify(partners_list)

@app.route('/api/products', methods=['GET'])
def api_products():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    products = c.fetchall()
    conn.close()
    
    products_list = []
    for product in products:
        products_list.append({
            'id': product[0],
            'name': product[1],
            'min_price': float(product[2])
        })
    
    return jsonify(products_list)

@app.route('/api/orders', methods=['GET'])
def api_orders():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT o.id, p.name, o.order_date, o.total_amount 
        FROM orders o 
        JOIN partners p ON o.partner_id = p.id 
        ORDER BY o.order_date DESC
    ''')
    orders = c.fetchall()
    conn.close()
    
    orders_list = []
    for order in orders:
        orders_list.append({
            'id': order[0],
            'partner_name': order[1],
            'order_date': order[2],
            'total_amount': float(order[3])
        })
    
    return jsonify(orders_list)

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def api_order_detail(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT o.id, p.name as partner_name, o.order_date, o.total_amount 
        FROM orders o 
        JOIN partners p ON o.partner_id = p.id 
        WHERE o.id = ?
    ''', (order_id,))
    order = c.fetchone()
    
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    c.execute('''
        SELECT pr.name, oi.quantity, oi.price 
        FROM order_items oi 
        JOIN products pr ON oi.product_id = pr.id 
        WHERE oi.order_id = ?
    ''', (order_id,))
    items = c.fetchall()
    
    conn.close()
    
    order_details = {
        'id': order[0],
        'partner_name': order[1],
        'order_date': order[2],
        'total_amount': float(order[3]),
        'items': []
    }
    
    for item in items:
        order_details['items'].append({
            'product_name': item[0],
            'quantity': item[1],
            'price': float(item[2]),
            'subtotal': float(item[1] * item[2])
        })
    
    return jsonify(order_details)

@app.route('/api/orders', methods=['POST', 'OPTIONS'])
def api_create_order():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        
        if not data or 'partner_id' not in data or 'items' not in data:
            return jsonify({'error': 'Invalid data'}), 400
        
        partner_id = data['partner_id']
        items = data['items']
        
        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        
        total_amount = 0
        for item in items:
            c.execute("SELECT min_price FROM products WHERE id = ?", (item['product_id'],))
            price = c.fetchone()[0]
            quantity = item['quantity']
            total_amount += price * quantity
        
        c.execute(
            "INSERT INTO orders (partner_id, order_date, total_amount) VALUES (?, ?, ?)",
            (partner_id, datetime.now().date(), total_amount)
        )
        order_id = c.lastrowid
        
        for item in items:
            c.execute("SELECT min_price FROM products WHERE id = ?", (item['product_id'],))
            price = c.fetchone()[0]
            c.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                (order_id, item['product_id'], item['quantity'], price)
            )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Order created successfully',
            'order_id': order_id,
            'total_amount': total_amount
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Web Interface
@app.route('/')
def index():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT o.id, p.name, o.order_date, o.total_amount 
        FROM orders o 
        JOIN partners p ON o.partner_id = p.id 
        ORDER BY o.order_date DESC
    ''')
    orders = c.fetchall()
    
    conn.close()
    return render_template('index.html', orders=orders)

@app.route('/order/<int:order_id>')
def order_detail(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT o.id, p.name as partner_name, o.order_date, o.total_amount 
        FROM orders o 
        JOIN partners p ON o.partner_id = p.id 
        WHERE o.id = ?
    ''', (order_id,))
    order = c.fetchone()
    
    c.execute('''
        SELECT pr.name, oi.quantity, oi.price 
        FROM order_items oi 
        JOIN products pr ON oi.product_id = pr.id 
        WHERE oi.order_id = ?
    ''', (order_id,))
    items = c.fetchall()
    
    conn.close()
    return render_template('order_detail.html', order=order, items=items)

@app.route('/create_order', methods=['GET', 'POST'])
def create_order():
    if request.method == 'POST':
        partner_id = request.form['partner_id']
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        
        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        
        total_amount = 0
        for i in range(len(product_ids)):
            c.execute("SELECT min_price FROM products WHERE id = ?", (product_ids[i],))
            price = c.fetchone()[0]
            quantity = int(quantities[i])
            total_amount += price * quantity
        
        c.execute(
            "INSERT INTO orders (partner_id, order_date, total_amount) VALUES (?, ?, ?)",
            (partner_id, datetime.now().date(), total_amount)
        )
        order_id = c.lastrowid
        
        for i in range(len(product_ids)):
            c.execute("SELECT min_price FROM products WHERE id = ?", (product_ids[i],))
            price = c.fetchone()[0]
            c.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                (order_id, product_ids[i], quantities[i], price)
            )
        
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM partners")
    partners = c.fetchall()
    c.execute("SELECT * FROM products")
    products = c.fetchall()
    conn.close()
    
    return render_template('create_order.html', partners=partners, products=products)

if __name__ == '__main__':
    print("Запуск приложения на http://localhost:5000")
    print("Доступные endpoints:")
    print("  GET  /                 - главная страница")
    print("  GET  /add_sample_data  - добавить тестовые данные")
    print("  GET  /api/partners     - список партнеров")
    print("  GET  /api/products     - список продуктов")
    print("  GET  /api/orders       - список заказов")
    print("  POST /api/orders       - создать заказ")
    app.run(debug=True, host='0.0.0.0', port=5000)