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