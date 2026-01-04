# 更新后的 app.py
# 添加多图片上传功能（最多10张），使用 JSON 存储图片路径列表
# products 表 images 字段为 TEXT，存储 JSON 数组
# 在添加/编辑时上传多个图片替换现有

from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 替换为你的密钥
app.config['UPLOAD_FOLDER'] = 'static/uploads'  # 图片上传目录
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_IMAGES'] = 12  # 最多10张

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
                  images TEXT,  -- JSON array of image paths
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

# 首页（添加分页）
@app.route('/')
def home():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    offset = (page - 1) * per_page
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM products")
    total = c.fetchone()[0]
    total_pages = (total // per_page) + (1 if total % per_page else 0)
    c.execute("SELECT p.id, p.name, c.name, p.price, p.description, p.images FROM products p JOIN categories c ON p.category_id = c.id LIMIT ? OFFSET ?", (per_page, offset))
    raw_products = c.fetchall()
    conn.close()
    # 解析 images JSON
    products = [(p[0], p[1], p[2], p[3], p[4], json.loads(p[5]) if p[5] else []) for p in raw_products]
    categories = get_categories()
    return render_template('home.html', products=products, categories=categories, page=page, total_pages=total_pages)

# 商品类别页
@app.route('/category/<int:category_id>')
def category(category_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT p.id, p.name, c.name, p.price, p.description, p.images FROM products p JOIN categories c ON p.category_id = c.id WHERE c.id = ?", (category_id,))
    raw_products = c.fetchall()
    c.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
    row = c.fetchone()
    category_name = row[0] if row else 'Unknown'
    conn.close()
    # 解析 images JSON
    products = [(p[0], p[1], p[2], p[3], p[4], json.loads(p[5]) if p[5] else []) for p in raw_products]
    return render_template('category.html', products=products, category=category_name)
# 商品详情页（显示多张图片）
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT p.id, p.name, c.name, p.price, p.description, p.images FROM products p JOIN categories c ON p.category_id = c.id WHERE p.id = ?", (product_id,))
    product = c.fetchone()
    conn.close()
    if product:
        images = json.loads(product[5]) if product[5] else []
        return render_template('product_detail.html', product=product, images=images)
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

# 添加商品（支持多图片上传）
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
        images = request.files.getlist('images')
        image_paths = []
        if len(images) > app.config['MAX_IMAGES']:
            flash(f'最多上传 {app.config["MAX_IMAGES"]} 张图片')
            return render_template('add_product.html', categories=categories)
        for image in images:
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_paths.append(f"uploads/{filename}")
        images_json = json.dumps(image_paths) if image_paths else None
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO products (name, category_id, price, description, images) VALUES (?, ?, ?, ?, ?)",
                  (name, category_id, price, description, images_json))
        conn.commit()
        conn.close()
        flash('商品添加成功')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_product.html', categories=categories)

# 编辑商品（支持多图片上传，替换现有）
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
        images = request.files.getlist('images')
        image_paths = []
        if images and images[0].filename:  # 如果上传新图片，则替换
            if len(images) > app.config['MAX_IMAGES']:
                flash(f'最多上传 {app.config["MAX_IMAGES"]} 张图片')
                c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
                product = c.fetchone()
                conn.close()
                return render_template('edit_product.html', product=product, categories=categories)
            for image in images:
                if image and allowed_file(image.filename):
                    filename = secure_filename(image.filename)
                    image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image_paths.append(f"uploads/{filename}")
        else:  # 无新上传，保留原有
            c.execute("SELECT images FROM products WHERE id = ?", (product_id,))
            existing_images = c.fetchone()[0]
            image_paths = json.loads(existing_images) if existing_images else []
        images_json = json.dumps(image_paths) if image_paths else None
        c.execute("UPDATE products SET name = ?, category_id = ?, price = ?, description = ?, images = ? WHERE id = ?",
                  (name, category_id, price, description, images_json, product_id))
        conn.commit()
        conn.close()
        flash('商品更新成功')
        return redirect(url_for('admin_dashboard'))
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    conn.close()
    images = json.loads(product[5]) if product[5] else []
    return render_template('edit_product.html', product=product, categories=categories, images=images)

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

# 编辑类别
@app.route('/admin/categories/edit/<int:category_id>', methods=['GET', 'POST'])
def edit_category(category_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        try:
            c.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
            conn.commit()
            flash('类别更新成功')
        except sqlite3.IntegrityError:
            flash('类别名称已存在')
        conn.close()
        return redirect(url_for('admin_categories'))
    c.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
    category = c.fetchone()
    conn.close()
    if category:
        return render_template('edit_category.html', category=category[0], category_id=category_id)
    else:
        flash('类别不存在')
        return redirect(url_for('admin_categories'))

# 删除类别
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

# 后台管理员管理
@app.route('/admin/users')
def admin_users():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id, username FROM users")
    users = c.fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

# 添加新管理员
@app.route('/admin/users/add', methods=['GET', 'POST'])
def add_user():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash('管理员添加成功')
        except sqlite3.IntegrityError:
            flash('用户名已存在')
        conn.close()
        return redirect(url_for('admin_users'))
    return render_template('add_user.html')

if __name__ == '__main__':
    app.run(debug=True)