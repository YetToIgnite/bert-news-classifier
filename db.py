import pymysql
from dbutils.pooled_db import PooledDB
import pymysql.cursors

# ======================
# 创建全局数据库连接池
# ======================
POOL = PooledDB(
    creator=pymysql,            # 使用链接数据库的模块
    maxconnections=15,          # 连接池允许的最大连接数，适合并发
    mincached=2,                # 初始化时，连接池中至少创建的空闲连接
    maxcached=5,                # 连接池中最多闲置的连接
    blocking=True,              # 如果连接池满了，是否阻塞等待直到有空闲连接
    ping=0,                     # 是否自动检查连接是否有效
    host='localhost',
    port=3306,
    user='root',
    password='wyk040911W.',         # ⚠️ 改成你的数据库密码
    database='news_system',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor  # 全局默认返回字典格式，极其方便
)

# ======================
# 获取数据库连接
# ======================
def get_db():
    """
    现在调用 get_db() 不会重新创建连接，
    而是从连接池中拿取一个现有连接！
    """
    return POOL.connection()


# ======================
# 自动初始化配置表 (新增)
# ======================
def init_config_tables():
    conn = get_db()
    cursor = conn.cursor()

    # 1. 新建动态分类表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS category_dict (
        id INT AUTO_INCREMENT PRIMARY KEY,
        category_name VARCHAR(50) NOT NULL UNIQUE,
        is_active TINYINT DEFAULT 1 COMMENT '1:显示, 0:隐藏'
    )''')

    # 2. 新建爬虫动态配置表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS spider_config (
        id INT AUTO_INCREMENT PRIMARY KEY,
        site_name VARCHAR(100) NOT NULL,
        target_url TEXT NOT NULL,
        status TINYINT DEFAULT 1 COMMENT '1:启用, 0:停用'
    )''')

    # 3. 写入默认分类（如果表为空）
    cursor.execute("SELECT COUNT(*) as cnt FROM category_dict")
    if cursor.fetchone()['cnt'] == 0:
        categories = ['财经', '房产', '股票', '教育', '科学', '社会', '政治', '体育', '游戏', '娱乐']
        for cat in categories:
            cursor.execute("INSERT INTO category_dict (category_name, is_active) VALUES (%s, 1)", (cat,))

    # 4. 写入默认爬虫网址（如果表为空，替代原本的 config.json）
    cursor.execute("SELECT COUNT(*) as cnt FROM spider_config")
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("INSERT INTO spider_config (site_name, target_url, status) VALUES (%s, %s, 1)",
                       ('新浪滚动新闻', 'https://news.sina.com.cn/roll/'))

    conn.commit()
    cursor.close()
    conn.close()


# 执行初始化
init_config_tables()