import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import re
import os
from newspaper import Article

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

    # 🌟 优化：增强过滤词库，拦截推广广告和无意义页面
    bad_words = [
        "首页", "客户端", "视频", "图片", "登录", "注册",
        "专题", "更多", "排行", "直播", "广告", "公告", "查看更多",
        "邮箱", "特权", "下载", "应用", "服务平台",
        # ⬇️ 新增：屏蔽人民网/新华网等媒体的多语言切换按钮与内部工具
        "Русский", "Português", "English", "Français", "智能创作", "Language"
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
# （核心优化）正文抓取函数：基于 newspaper3k + BeautifulSoup 双重保障
# =========================
def get_news_content(url):
    # 方案 A: 优先使用 newspaper3k 智能提取
    try:
        article = Article(url, language='zh')
        article.download()
        article.parse()
        text = article.text.replace('\n', ' ').strip()

        # 如果提取出的正文长度大于 20 个字，认为提取成功
        if len(text) > 20:
            return text
    except Exception as e:
        print(f"🔄 智能提取受阻，尝试备用方案: {url}")

    # 方案 B: newspaper3k 失败时，回退到原有的 BeautifulSoup 提取逻辑
    try:
        html = fetch(url)
        if not html:
            return ""

        soup = BeautifulSoup(html, "html.parser")

        # 删除垃圾标签
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "video"]):
            tag.decompose()

        bad_keywords = [
            "版权所有", "Copyright", "登录", "注册",
            "意见反馈", "广告", "举报邮箱",
            "新浪公司", "免责声明", "收藏", "责任编辑"
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
        print("❌ 正文彻底抓取失败:", url, e)
        return ""