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

    # 2. 新建爬虫动态配置表 (保证表存在)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS spider_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            site_name VARCHAR(100) NOT NULL,
            target_url TEXT NOT NULL,
            status TINYINT DEFAULT 1 COMMENT '1:启用, 0:停用'
        )''')

    # 🌟 核心修复：自动检测旧版数据库结构并升级表字段
    try:
        # 尝试查询新加入的 base_url 和 article_selector 字段
        cursor.execute("SELECT base_url, article_selector FROM spider_config LIMIT 1")
    except Exception as e:
        print("检测到旧版数据库结构，正在自动升级 spider_config 表...")
        # 如果报错（说明没有这俩字段），则执行 ALTER TABLE 动态追加
        cursor.execute("ALTER TABLE spider_config ADD COLUMN base_url TEXT AFTER target_url")
        cursor.execute("ALTER TABLE spider_config ADD COLUMN article_selector VARCHAR(100) DEFAULT 'a' AFTER base_url")
        conn.commit()
        print("数据库表结构升级成功！")

    # 3. 写入默认分类（如果表为空）
    cursor.execute("SELECT COUNT(*) as cnt FROM category_dict")
    if cursor.fetchone()['cnt'] == 0:
        categories = ['财经', '房产', '股票', '教育', '科学', '社会', '政治', '体育', '游戏', '娱乐']
        for cat in categories:
            cursor.execute("INSERT INTO category_dict (category_name, is_active) VALUES (%s, 1)", (cat,))

    # 4. 写入默认爬虫网址（如果表为空）
    cursor.execute("SELECT COUNT(*) as cnt FROM spider_config")
    if cursor.fetchone()['cnt'] == 0:
        try:
            cursor.execute(
                "INSERT INTO spider_config (site_name, target_url, base_url, article_selector, status) VALUES (%s, %s, %s, %s, %s)",
                ('新浪滚动', 'https://news.sina.com.cn/roll/', 'https://news.sina.com.cn/', 'ul.list_009 li a', 1)
            )
        except:
            # 兼容老版插入
            cursor.execute(
                "INSERT INTO spider_config (site_name, target_url, status) VALUES (%s, %s, %s)",
                ('新浪滚动', 'https://news.sina.com.cn/roll/', 1)
            )

    conn.commit()
    cursor.close()
    conn.close()


# 执行初始化
init_config_tables()