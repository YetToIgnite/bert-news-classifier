import pymysql

def get_db():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='wyk040911W.',
        database='news_system',
        charset='utf8mb4',
        use_unicode=True,
        init_command="SET NAMES utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )