from crawler.crawler import crawl_news
import json

# 读取配置
with open("crawler/config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# 取第一个网站测试
site = config["sites"][0]

news_list = crawl_news(site, max_news=5)

for news in news_list:
    print(news)