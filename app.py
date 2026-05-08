from flask import Flask, request, jsonify, render_template, session, redirect, Response
from predict import predict
from datetime import datetime
import pymysql
from wordcloud import WordCloud
from news_service import run_news_pipeline
from queue import Queue
import threading
import os
import json
from db import get_db
from predict import predict, save_record

app = Flask(__name__)
app.secret_key = '123456'

# ======================
# 注册
# ======================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return "用户名或密码不能为空"

        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM user WHERE username=%s", (username,))
        if cursor.fetchone():
            return "用户名已存在"

        cursor.execute("INSERT INTO user (username, password) VALUES (%s, %s)", (username, password))
        db.commit()

        cursor.close()
        db.close()

        return redirect('/login')

    return render_template('register.html')


# ======================
# 登录
# ======================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM user WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user:
            session['user'] = username
            return redirect('/')
        else:
            return "登录失败"

    return render_template('login.html')


# ======================
# 登出
# ======================
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')


# ======================
# 首页
# ======================
@app.route('/')
def home():
    if 'user' not in session:
        return redirect('/login')
    return render_template('index.html')


# ======================
# 预测接口
# ======================
@app.route('/predict', methods=['POST'])
def classify():
    try:
        print("\n===== predict请求开始 =====")

        if 'user' not in session:
            print("❌ 用户未登录")
            return jsonify({
                'label': '未登录',
                'confidence': 0,
                'top3': []
            })

        data = request.get_json()
        text = data.get('text', '')

        print("用户:", session['user'])
        print("输入文本:", text)

        if not text or not text.strip():
            return jsonify({
                'label': '空输入',
                'confidence': 0,
                'top3': []
            })

        # ======================
        # 核心预测（重点）
        # ======================
        results = predict(text, username=session['user'])

        print("预测结果:", results)

        # Top1
        label = results[0][0]
        confidence = float(results[0][1])

        response = {
            'label': label,
            'confidence': confidence,
            'top3': [
                [i[0], float(i[1])] for i in results
            ]
        }

        # ======================
        # ✔ 关键修复：数据库错误不影响返回
        # ======================
        try:
            save_record(
                text,
                label,
                confidence,
                session['user']
            )
        except Exception as e:
            print("⚠️ 数据库写入失败（已忽略）:", e)

        print("返回结果:", response)
        print("===== predict请求结束 =====\n")

        return jsonify(response)

    except Exception as e:
        print("❌ predict接口异常:", str(e))
        return jsonify({
            'label': '系统错误',
            'confidence': 0,
            'top3': []
        })


# ======================
# 页面
# ======================
@app.route('/history')
def history():
    if 'user' not in session:
        return redirect('/login')

    user = session['user']

    # 获取参数
    page = int(request.args.get('page', 1))
    keyword = request.args.get('keyword', '')

    limit = 10
    offset = (page - 1) * limit

    db = get_db()
    cursor = db.cursor()

    # 总数
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM click_log
        WHERE username=%s AND title LIKE %s
    """, (user, f"%{keyword}%"))

    total = cursor.fetchone()['count']
    total_pages = (total + limit - 1) // limit

    # 数据
    cursor.execute("""
        SELECT id, title, url, label, create_time
        FROM click_log
        WHERE username=%s AND title LIKE %s
        ORDER BY id DESC
        LIMIT %s OFFSET %s
    """, (user, f"%{keyword}%", limit, offset))

    data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        'history.html',
        data=data,
        page=page,
        total_pages=total_pages,
        keyword=keyword
    )

@app.route('/delete/<int:id>')
def delete(id):
    if 'user' not in session:
        return redirect('/login')

    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM click_log WHERE id=%s", (id,))
    db.commit()

    cursor.close()
    db.close()

    return redirect('/history')

@app.route('/stats_page')
def stats_page():
    if 'user' not in session:
        return redirect('/login')
    return render_template('stats.html')


@app.route('/stats')
def stats():
    if 'user' not in session:
        return jsonify({'labels': [], 'values': []})

    user = session['user']

    try:
        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT label, COUNT(*) as count
            FROM click_log
            WHERE username=%s
            GROUP BY label
        """, (user,))

        data = cursor.fetchall()

        cursor.close()
        db.close()

        # ⭐ 改这里（DictCursor写法）
        labels = [row['label'] for row in data]
        values = [row['count'] for row in data]

        print("统计结果:", labels, values)

        return jsonify({'labels': labels, 'values': values})

    except Exception as e:
        print("统计报错:", e)
        return jsonify({'labels': [], 'values': []})


@app.route('/wordcloud_page')
def wordcloud_page():
    if 'user' not in session:
        return redirect('/login')

    categories = ["财经", "房产", "股票", "教育", "科学", "社会", "政治", "体育", "游戏", "娱乐"]
    return render_template("wordcloud_page.html", categories=categories)


# ======================
# 词云
# ======================
WORDCLOUD_DIR = "static/wordclouds"
os.makedirs(WORDCLOUD_DIR, exist_ok=True)

def generate_wordcloud(category):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT title FROM click_log
        WHERE label=%s
    """, (category,))

    rows = cursor.fetchall()

    cursor.close()
    db.close()

    text = " ".join([row['title'] for row in rows]) or "暂无数据"

    wc = WordCloud(
        width=800,
        height=400,
        background_color="white",
        font_path="msyh.ttc"
    ).generate(text)

    path = os.path.join(WORDCLOUD_DIR, f"{category}.png")
    wc.to_file(path)

    return "/" + path.replace("\\", "/")


@app.route('/wordcloud/<category>')
def show_wordcloud(category):
    if 'user' not in session:
        return redirect('/login')

    img = generate_wordcloud(category)
    return render_template("wordcloud.html", img_path=img, category=category)


# ======================
# ⭐ 获取网站列表
# ======================
@app.route("/sites")
def get_sites():
    with open("crawler/config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    return jsonify(config["sites"])


# ======================
# ⭐ 新闻进度流（核心）
# ======================
@app.route('/news_stream')
def news_stream():

    q = Queue()

    # ✅ 从URL取参数（不是json）
    selected_sites = request.args.get("sites", "")
    selected_sites = selected_sites.split(",") if selected_sites else []

    def progress(msg):
        q.put(msg)

    def worker():
        result = run_news_pipeline(selected_sites, progress_callback=progress)
        q.put({"done": True, "result": result})

    threading.Thread(target=worker).start()

    def generate():
        while True:
            msg = q.get()
            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"

            if isinstance(msg, dict) and msg.get("done"):
                break

    return Response(generate(), mimetype='text/event-stream')


# ======================
# 新闻页面
# ======================
@app.route('/news_page')
def news_page():
    if 'user' not in session:
        return redirect('/login')
    return render_template('news.html')


# ======================
# 点击记录
# ======================
@app.route('/click_log', methods=['POST'])
def click_log():
    if 'user' not in session:
        return jsonify({'status': 'error'})

    try:
        data = request.get_json()

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO click_log (username, title, url, label, create_time)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            session['user'],
            data.get('title'),
            data.get('url'),
            data.get('label'),
            datetime.now()
        ))

        db.commit()

        cursor.close()
        db.close()

        return jsonify({'status': 'ok'})

    except Exception as e:
        print("点击记录失败:", e)
        return jsonify({'status': 'error'})

# ======================
# 用户推荐
# ======================
@app.route('/recommend')
def recommend():
    if 'user' not in session:
        return jsonify([])

    user = session['user']
    db = get_db()
    cursor = db.cursor()

    try:
        # ======================
        # 1️⃣ 获取用户兴趣
        # ======================
        cursor.execute("""
            SELECT label, COUNT(*) as cnt
            FROM click_log
            WHERE username=%s
            GROUP BY label
            ORDER BY cnt DESC
            LIMIT 3
        """, (user,))

        rows = cursor.fetchall()
        categories = [r['label'] for r in rows]

        # ======================
        # 2️⃣ 冷启动（没点击过）
        # ======================
        if not categories:
            cursor.execute("""
                SELECT title, url, category as label
                FROM news
                ORDER BY crawl_time DESC
                LIMIT 10
            """)
            return jsonify(cursor.fetchall())

        # ======================
        # 3️⃣ 推荐新闻
        # ======================
        format_strings = ','.join(['%s'] * len(categories))

        query = f"""
            SELECT title, url, category as label
            FROM news
            WHERE category IN ({format_strings})
            AND title NOT IN (
                SELECT title FROM click_log WHERE username=%s
            )
            ORDER BY crawl_time DESC
            LIMIT 10
        """

        cursor.execute(query, (*categories, user))
        result = cursor.fetchall()

        return jsonify(result)

    except Exception as e:
        print("推荐错误:", e)
        return jsonify([])

    finally:
        cursor.close()
        db.close()


# ======================
# 启动
# ======================
if __name__ == '__main__':
    app.run(debug=True)