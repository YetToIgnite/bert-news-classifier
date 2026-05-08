import json
from collections import defaultdict
from datetime import datetime

from crawler.crawler import crawl_news, get_news_content
from predict import predict_label
from db import get_db


# =========================
# 新闻处理主流程
# =========================
def run_news_pipeline(selected_sites=None, progress_callback=None):

    # =========================
    # 读取配置
    # =========================
    with open("crawler/config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    sites = config["sites"]

    if selected_sites:
        sites = [s for s in sites if s["name"] in selected_sites]

    all_news = []

    # =========================
    # 1️⃣ 爬取新闻列表
    # =========================
    for idx, site in enumerate(sites):

        if progress_callback:
            progress_callback({
                "site": site["name"],
                "status": "start",
                "progress": int(idx / len(sites) * 100)
            })

        news_list = crawl_news(site, max_news=30)
        all_news.extend(news_list)

        if progress_callback:
            progress_callback({
                "site": site["name"],
                "status": "done",
                "progress": int((idx + 1) / len(sites) * 100)
            })

    # =========================
    # 2️⃣ 分类 + 入库
    # =========================
    db = get_db()
    cursor = db.cursor()

    results = []

    for news in all_news:

        title = news.get("title", "")
        url = news.get("url", "")

        if not title:
            continue

        # =========================
        # ⭐ 获取正文（关键修复点）
        # =========================
        content = get_news_content(url)
        if not content:
            content = ""

        # 截断防止过长
        content = content[:300]

        # =========================
        # ⭐ 融合文本（标题 + 正文）
        # =========================
        text = title + " " + content

        # =========================
        # BERT分类
        # =========================
        label = predict_label(text)

        item = {
            "title": title,
            "summary": content,
            "label": label,
            "url": url
        }

        results.append(item)

        # =========================
        # 写入数据库
        # =========================
        try:
            cursor.execute("""
                INSERT INTO news (title, content, url, category, publish_time)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                title,
                content,
                url,
                label,
                datetime.now()
            ))
        except Exception as e:
            print("入库失败:", e)

    db.commit()
    cursor.close()
    db.close()

    # =========================
    # 3️⃣ 按类别整理返回
    # =========================
    category_map = defaultdict(list)

    for item in results:
        category_map[item["label"]].append(item)

    final_result = {
        label: items[:10]
        for label, items in category_map.items()
    }

    return final_result