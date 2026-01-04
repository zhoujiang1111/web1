# 更新后的 app.py（仅修正 category 路由中的 bug，其他不变）

from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 替换为你的密钥
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # 图片上传目录
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 数据库初始化
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  category_id INTEGER NOT NULL,
                  price REAL NOT NULL,
                  description TEXT,
                  image TEXT,
                  FOREIGN KEY (category_id) REFERENCES categories(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')
    # 添加默认管理员
    try:
        c.execute("INSERT INTO users (username, password) VALUES ('admin', 'admin')")
    except sqlite3.IntegrityError:
        pass  # 已存在
    # 添加默认类别（可选）
    try:
        c.execute("INSERT INTO categories (name) VALUES ('electronics')")
        c.execute("INSERT INTO categories (name) VALUES ('clothing')")
    except sqlite3.IntegrityError:
        pass
    conn.commit()
    conn.close()

init_db()

# 检查文件扩展名
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# 获取所有类别
def get_categories():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM categories")
    categories = c.fetchall()
    conn.close()
    return categories

# 首页
@app.route('/')
def home():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT p.id, p.name, c.name, p.price, p.description, p.image FROM products p JOIN categories c ON p.category_id = c.id LIMIT 1000")
    products = c.fetchall()
    conn.close()
    categories = get_categories()
    return render_template('home.html', products=products, categories=categories)

# 商品类别页（修正 bug）
@app.route('/category/<int:category_id>')
def category(category_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT p.id, p.name, c.name, p.price, p.description, p.image FROM products p JOIN categories c ON p.category_id = c.id WHERE c.id = ?", (category_id,))
    products = c.fetchall()
    c.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
    row = c.fetchone()
    category_name = row[0] if row else 'Unknown'
    conn.close()
    return render_template('category.html', products=products, category=category_name)

# 商品详情页
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT p.id, p.name, c.name, p.price, p.description, p.image FROM products p JOIN categories c ON p.category_id = c.id WHERE p.id = ?", (product_id,))
    product = c.fetchone()
    conn.close()
    if product:
        return render_template('product_detail.html', product=product)
    else:
        flash('商品不存在')
        return redirect(url_for('home'))

# 后台登录
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['logged_in'] = True
            flash('登录成功')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('用户名或密码错误')
    return render_template('login.html')

# 后台注销
@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    flash('已注销')
    return redirect(url_for('home'))

# 后台仪表盘（列出所有商品）
@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT p.id, p.name, c.name, p.price FROM products p JOIN categories c ON p.category_id = c.id")
    products = c.fetchall()
    conn.close()
    return render_template('admin.html', products=products)

# 添加商品
@app.route('/admin/add', methods=['GET', 'POST'])
def add_product():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    categories = get_categories()
    if request.method == 'POST':
        name = request.form['name']
        category_id = int(request.form['category_id'])
        price = float(request.form['price'])
        description = request.form['description']
        image = request.files['image']
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = f"uploads/{filename}"
        else:
            image_path = None
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO products (name, category_id, price, description, image) VALUES (?, ?, ?, ?, ?)",
                  (name, category_id, price, description, image_path))
        conn.commit()
        conn.close()
        flash('商品添加成功')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_product.html', categories=categories)

# 编辑商品
@app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    categories = get_categories()
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        category_id = int(request.form['category_id'])
        price = float(request.form['price'])
        description = request.form['description']
        image = request.files['image']
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = f"uploads/{filename}"
            c.execute("UPDATE products SET image = ? WHERE id = ?", (image_path, product_id))
        c.execute("UPDATE products SET name = ?, category_id = ?, price = ?, description = ? WHERE id = ?",
                  (name, category_id, price, description, product_id))
        conn.commit()
        conn.close()
        flash('商品更新成功')
        return redirect(url_for('admin_dashboard'))
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    conn.close()
    return render_template('edit_product.html', product=product, categories=categories)

# 删除商品
@app.route('/admin/delete/<int:product_id>')
def delete_product(product_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    flash('商品删除成功')
    return redirect(url_for('admin_dashboard'))

# 后台类别管理
@app.route('/admin/categories')
def admin_categories():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    categories = get_categories()
    return render_template('admin_categories.html', categories=categories)

# 添加类别
@app.route('/admin/categories/add', methods=['GET', 'POST'])
def add_category():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        name = request.form['name']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            conn.commit()
            flash('类别添加成功')
        except sqlite3.IntegrityError:
            flash('类别已存在')
        conn.close()
        return redirect(url_for('admin_categories'))
    return render_template('add_category.html')

# 删除类别（注意：如果有商品关联，会失败，因为外键约束）
@app.route('/admin/categories/delete/<int:category_id>')
def delete_category(category_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    try:
        c.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        flash('类别删除成功')
    except sqlite3.IntegrityError:
        flash('无法删除：有商品关联此类别')
    conn.close()
    return redirect(url_for('admin_categories'))

if __name__ == '__main__':
    app.run(debug=True)
	
