import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import re
import os

os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""


# =========================
# 请求函数
# =========================
def fetch(url):
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(
            url,
            headers=headers,
            timeout=10,
            proxies={"http": None, "https": None}
        )
        res.encoding = res.apparent_encoding
        return res.text
    except Exception as e:
        print("请求失败:", url, e)
        return ""


# =========================
# 文本清洗
# =========================
def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n|\t|\r", " ", text)
    text = re.sub(r"广告|点击|查看更多|客户端|登录|注册", "", text)

    return text.strip()


# =========================
# 抓新闻列表（标题 + URL）
# =========================
def crawl_news(site_config, max_news=30):

    html = fetch(site_config["url"])
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    links = soup.select(site_config.get("article_selector", "a"))

    news_list = []
    seen = set()

    bad_words = [
        "首页", "客户端", "视频", "图片", "登录", "注册",
        "专题", "更多", "排行", "直播", "广告", "公告", "查看更多"
    ]

    for link in links:

        title = clean_text(link.get_text())
        href = link.get("href")

        if not title or not href:
            continue

        if len(title) < 8:
            continue

        if any(w in title for w in bad_words):
            continue

        if any(x in href for x in ["javascript", "weibo", "photo", "video"]):
            continue

        full_url = urljoin(site_config["base_url"], href)

        if full_url in seen:
            continue
        seen.add(full_url)

        news_list.append({
            "title": title,
            "url": full_url
        })

        if len(news_list) >= max_news:
            break

        time.sleep(0.1)

    return news_list


# =========================
# （可选）正文抓取函数（给 news_service 用）
# =========================
def get_news_content(url):
    try:
        html = fetch(url)
        if not html:
            return ""

        soup = BeautifulSoup(html, "html.parser")

        # ❌ 删除垃圾标签
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # ❌ 去掉明显无关文本
        bad_keywords = [
            "版权所有", "Copyright", "登录", "注册",
            "意见反馈", "广告", "举报邮箱",
            "新浪公司", "免责声明", "收藏"
        ]

        paragraphs = soup.find_all("p")

        texts = []
        for p in paragraphs:
            t = p.get_text().strip()

            if len(t) < 10:
                continue

            if any(k in t for k in bad_keywords):
                continue

            texts.append(t)

        return " ".join(texts)

    except Exception as e:
        print("正文抓取失败:", url, e)
        return ""