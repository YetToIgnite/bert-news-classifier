import json
from collections import defaultdict
from datetime import datetime
import concurrent.futures  # 🌟 新增：引入 Python 原生并发库

from crawler.crawler import crawl_news, get_news_content
from predict import predict_label
from db import get_db


# =========================
# 新闻处理主流程 (支持多线程并发优化)
# =========================
def run_news_pipeline(selected_sites=None, progress_callback=None):
    # =========================
    # 🌟 核心升级：从 MySQL 动态读取配置，彻底废弃 config.json
    # =========================
    try:
        db = get_db()
        cursor = db.cursor()
        # 仅拉取管理员后台设置为“启用” (status=1) 的站点
        cursor.execute("SELECT * FROM spider_config WHERE status=1")
        db_sites = cursor.fetchall()
        cursor.close()
        db.close()
    except Exception as e:
        print("读取数据库爬虫配置失败:", e)
        return {}

    # 将数据库字段映射为 crawler.py 需要的字典格式
    sites = []
    for row in db_sites:
        sites.append({
            "name": row["site_name"],
            "url": row["target_url"],
            "base_url": row["base_url"] if row.get("base_url") else row["target_url"],
            "article_selector": row["article_selector"] if row.get("article_selector") else "a"
        })

    # 根据前端勾选的站点进行过滤
    if selected_sites:
        sites = [s for s in sites if s["name"] in selected_sites]

    if not sites:
        if progress_callback:
            progress_callback({"site": "错误：未匹配到任何启用的爬虫任务", "status": "done", "progress": 100})
        return {}

    all_news = []

    # =========================
    # 1️⃣ 爬取新闻列表 (仅获取标题和链接)
    # =========================
    for idx, site in enumerate(sites):
        if progress_callback:
            progress_callback({
                "site": site["name"] + " (列表获取)",
                "status": "start",
                "progress": int(idx / len(sites) * 30)  # 进度条分配 30% 给列表爬取
            })

        news_list = crawl_news(site, max_news=30)
        all_news.extend(news_list)

    if not all_news:
        return {}

    # =========================
    # 2️⃣ ⭐ 核心优化：多线程并发拉取正文 (IO 密集型任务)
    # =========================
    if progress_callback:
        progress_callback({
            "site": f"开启多线程拉取 {len(all_news)} 篇正文...",
            "status": "start",
            "progress": 40
        })

    # 定义单个网页的拉取任务
    def fetch_single_content(news_item):
        content = get_news_content(news_item["url"])
        news_item["content"] = content if content else ""
        return news_item

    # 🌟 创建包含 10 个线程的线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # map 函数会自动将 all_news 分发给 10 个线程并发执行，并阻塞等待所有执行完毕
        all_news_with_content = list(executor.map(fetch_single_content, all_news))

    # =========================
    # 3️⃣ 分类 + 入库 (CPU/GPU 密集型任务，保持串行确保 PyTorch 稳定)
    # =========================
    db = get_db()
    cursor = db.cursor()
    results = []

    total_items = len(all_news_with_content)

    for idx, news in enumerate(all_news_with_content):
        # 更新进度条
        if progress_callback and idx % 5 == 0:  # 每处理 5 条更新一次，防止前端卡顿
            progress_callback({
                "site": f"AI 模型推理分析中 ({idx}/{total_items})...",
                "status": "process",
                "progress": 50 + int((idx / total_items) * 45)
            })

        title = news.get("title", "")
        url = news.get("url", "")
        content = news.get("content", "")[:300]  # 截断防止过长

        if not title:
            continue

        text = title + " " + content

        # 🌟 BERT 分类推理
        label = predict_label(text)

        item = {
            "title": title,
            "summary": content,
            "label": label,
            "url": url
        }
        results.append(item)

        # 🌟 写入数据库
        try:
            cursor.execute("""
                INSERT INTO news (title, content, url, category, publish_time)
                VALUES (%s, %s, %s, %s, %s)
            """, (title, content, url, label, datetime.now()))
        except Exception as e:
            # 忽略重复主键等错误，防止中断
            pass

    db.commit()
    cursor.close()
    db.close()

    if progress_callback:
        progress_callback({"site": "全部分析完成", "status": "done", "progress": 100})

    # =========================
    # 4️⃣ 按类别整理返回
    # =========================
    category_map = defaultdict(list)
    for item in results:
        category_map[item["label"]].append(item)

    return {label: items[:10] for label, items in category_map.items()}