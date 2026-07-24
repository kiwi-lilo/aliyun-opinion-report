import os
import re
import csv
import time
import requests
import smtplib
from urllib.parse import urljoin
from datetime import datetime, timedelta, timezone
from hashlib import md5
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr
from collections import defaultdict

EMAIL_CONFIG = {
    "enabled":     True,
    "smtp_server": "smtp.qq.com",               # 如果你是QQ邮箱就填 smtp.qq.com，网易是 smtp.163.com
    "smtp_port":   465,                         # 通常使用465端口
    "sender":      "782319269@qq.com",         # 【改成你的发件邮箱地址】
    "password":    "jhdrjcrxhyecbcae",       # 【改成你的邮箱授权码，注意不是登录密码！】
    "receivers":   ["782319269@qq.com", "18821775766@163.com"], 
}

# 涉陕关键词矩阵
SHAANXI_KEYWORDS = ["陕西", "西安", "咸阳", "宝鸡", "渭南", "延安", "榆林", "汉中", "安康", "商洛", "铜川", "杨凌"]

# ==========================================
# 2. 全网暴力抓取目标矩阵
# ==========================================
# A库：纯陕西地方频道（只要日期对，默认全部视为涉陕报道）
LOCAL_CHANNELS = {
    "新华网": ["http://sn.news.cn/"],
    "人民网": ["http://sn.people.com.cn/"],
    "央广网": ["http://www.cnr.cn/shaanxi/"], # <-- 已更新为央广网最新陕西频道
    "中国新闻网": ["http://www.shx.chinanews.com.cn/"],
    "国际在线": ["http://sn.cri.cn/"],
    "光明网": ["https://difang.gmw.cn/sn/"],
}

# B库：各大央媒全国主网频道（不仅日期要对，标题必须包含陕西关键词才收录）
MAIN_CHANNELS = {
    "人民网": ["http://society.people.com.cn/", "http://politics.people.com.cn/"],
    "新华网": ["http://www.news.cn/local/", "http://www.news.cn/politics/"],
    "央视网": ["https://news.cctv.com/", "https://news.cctv.com/local/"],
    "中国经济网": ["http://district.ce.cn/", "http://www.ce.cn/"],
    "光明网": ["https://difang.gmw.cn/", "https://politics.gmw.cn/"],
    "中国青年报": ["http://news.cyol.com/"],
    "中国新闻网": ["http://www.chinanews.com.cn/"],
    "经济日报": ["http://www.ce.cn/cysc/"],
    "央广网": ["https://www.cnr.cn/"]  # <-- 新增：央广网全国主站
}

NEWS_CATEGORIES = {
    "💼 经济/产业": ["经济", "产业", "高质量发展", "项目", "投资", "企业", "产值", "农业", "工业", "新能源"],
    "🌸 文旅/生态": ["旅游", "文化", "生态", "秦岭", "黄河", "非遗", "景区", "文物", "博物馆", "绿化"],
    "👥 民生/社会": ["民生", "教育", "医疗", "就业", "群众", "社区", "交通", "天气", "暴雨", "救援"],
    "⭐ 时政/党建": ["会议", "强调", "调研", "党建", "干部", "落实", "精神", "视察", "改革"],
}

# ==========================================
# 3. 日期与解析模块
# ==========================================
def get_date_range():
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return today, yesterday

def get_url_date_patterns():
    """涵盖所有央媒的网址日期格式"""
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz)
    dates = [now, now - timedelta(days=1)]
    patterns = []
    for d in dates:
        patterns.extend([
            d.strftime("%Y/%m%d"), d.strftime("%Y-%m/%d"), d.strftime("%Y%m%d"), 
            d.strftime("%Y-%m-%d"), d.strftime("%Y%m/%d"), d.strftime("%Y/%m/%d")
        ])
    return patterns

def analyze_news(text):
    tags = set()
    for cat, kws in NEWS_CATEGORIES.items():
        if any(kw in text for kw in kws):
            tags.add(cat)
            break
    if not tags: tags.add("📰 综合资讯")
    return list(tags)

def _clean(text):
    text = re.sub(r'<[^>]+>', '', text).strip()
    return re.sub(r'\s+', ' ', text)

# ==========================================
# 4. 暴力提取引擎核心
# ==========================================
# ==========================================
# 4. 暴力提取引擎核心
# ==========================================
def extract_news_from_url(media_name, url, date_patterns, is_local_channel):
    """
    is_local_channel=True: 地方频道，只校验日期
    is_local_channel=False: 全国频道，校验日期 + 标题必须有陕西关键词
    """
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36"}
    
    try:
        # 强制直连，无视代理
        r = requests.get(url, headers=headers, timeout=15, proxies={"http": None, "https": None})
        
        # 🚨 核心修复：彻底告别乱码！
        # 如果服务器没有明确告知编码，放弃脆弱的正则，使用 requests 内置的内容智能推断器
        if r.encoding == 'ISO-8859-1' or not r.encoding:
            r.encoding = r.apparent_encoding or 'utf-8'
        
        # 暴力提取网页所有 <a> 标签
        links = re.findall(r'<a\s+[^>]*href=["\'](.*?)["\'][^>]*>(.*?)</a>', r.text, re.I | re.S)
        
        for href, title in links:
            title = _clean(title)
            if len(title) < 5 or "更多" in title or "首页" in title: 
                continue
                
            full_url = urljoin(url, href)
            
            if not any(pat in full_url for pat in date_patterns):
                continue
                
            if not is_local_channel:
                if not any(kw in title for kw in SHAANXI_KEYWORDS):
                    continue
                    
            results.append({
                "id": md5(full_url.encode()).hexdigest()[:16],
                "title_hash": md5(title.encode()).hexdigest()[:16],
                "media_std": media_name, 
                "user": f"{media_name}官网", 
                "text": f"【{title}】", 
                "time": "今日/昨日最新发布", 
                "type": "官网文章", 
                "url": full_url
            })
    except Exception as e:
        print(f"  [请求异常] {media_name} ({url}): {e}")
        
    return results

# ==========================================
# 5. 生成报表与邮件发送
# ==========================================
def save_files(results, report_date_str):
    ts = datetime.now().strftime("%H%M%S")
    files = []
    if results:
        fn = f"央媒官网涉陕报道_{report_date_str}_{ts}.csv"
        with open(fn, "w", encoding="utf-8-sig", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["所属央媒", "发布渠道", "新闻分类", "内容", "链接"])
            for w in results:
                wr.writerow([w["media_std"], w["type"], ", ".join(w["tags"]), w["text"], w["url"]])
        files.append(fn)
    return files

def build_html_report(results, report_date_str):
    if not results: return f"<h3>{report_date_str} 暂未监测到央媒官网发布涉陕报道。</h3>"
    
    grouped_news = defaultdict(list)
    for w in results: grouped_news[w["media_std"]].append(w)

    news_html = ""
    for media_name, news_list in sorted(grouped_news.items(), key=lambda x: len(x[1]), reverse=True):
        news_html += f"""
        <div style="margin-bottom: 25px; border: 1px solid #e1e4e8; border-radius: 6px; overflow: hidden;">
            <div style="background-color: #f6f8fa; padding: 10px 15px; border-bottom: 1px solid #e1e4e8; font-weight: bold; color: #0366d6; font-size: 16px;">
                📰 {media_name} <span style="font-size:13px; color:#666; font-weight:normal;">({len(news_list)}篇)</span>
            </div>
            <div style="padding: 0 15px;">
        """
        for idx, w in enumerate(news_list, 1):
            tag_str = "".join([f'<span style="background:#e8f0fe; color:#1a73e8; padding:2px 8px; border-radius:12px; font-size:12px; margin-right:5px;">{t}</span>' for t in w["tags"]])
            border_bottom = "border-bottom: 1px dashed #eaecef;" if idx < len(news_list) else ""
            
            news_html += f"""
                <div style="padding: 12px 0; {border_bottom}">
                    <div style="font-size: 14px; color: #24292e; line-height: 1.6; margin-bottom: 8px;">
                        <span style="background:#28a745; color:#fff; padding:2px 6px; border-radius:4px; font-size:12px; margin-right:5px;">官网文章</span>{w["text"]}
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>{tag_str}</div>
                        <div style="font-size: 12px; color: #586069;">
                            <a href="{w["url"]}" style="color: #0366d6; text-decoration: none;" target="_blank">原文 🔗</a>
                        </div>
                    </div>
                </div>
            """
        news_html += "</div></div>"

    return f"""
    <!DOCTYPE html>
    <html><head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333;">
        <div style="background: linear-gradient(135deg, #28a745, #218838); color: #fff; padding: 25px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
            <h1 style="margin: 0; font-size: 24px; letter-spacing: 2px;">🗞️ 央媒官网涉陕监测早报</h1>
            <p style="margin: 10px 0 0; font-size: 14px; opacity: 0.9;">监测日期：{report_date_str} &nbsp;|&nbsp; 共提取报道：{len(results)} 篇</p>
        </div>
        {news_html}
    </body>
    </html>
    """

def send_email(subject, html_body, files):
    cfg = EMAIL_CONFIG
    if not cfg["sender"] or not cfg["password"] or not cfg["receivers"] or cfg["receivers"] == [""]:
        print("  ⚠️ 邮箱未配置完全，测试运行完毕。")
        return
    msg = MIMEMultipart()
    msg["From"] = formataddr((str(Header("央媒官网监测机器人", "utf-8")), cfg["sender"]))
    msg["To"] = ", ".join(cfg["receivers"])
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    
    if files:
        for fp in files:
            if os.path.exists(fp):
                with open(fp, "rb") as f: 
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment", filename=os.path.basename(fp))
                msg.attach(part)
    try:
        server = smtplib.SMTP_SSL(cfg["smtp_server"], cfg["smtp_port"], timeout=30) if cfg["smtp_port"] == 465 else smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"], timeout=30)
        if cfg["smtp_port"] != 465: server.starttls()
        server.login(cfg["sender"], cfg["password"])
        server.sendmail(cfg["sender"], cfg["receivers"], msg.as_string())
        server.quit()
        print("  ✅ 邮件自动发送成功！")
    except Exception as e: 
        print(f"  ❌ 邮件失败: {e}")

# ==========================================
# 6. 主程序逻辑
# ==========================================
def main():
    today, yesterday = get_date_range()
    date_patterns = get_url_date_patterns()
    report_str = f"{yesterday}至{today}"
    
    print(f" 🚀 央媒官网全矩阵巡检系统启动 | 目标日期: {report_str}")
    print("=" * 60)
    
    final_results = []
    seen_urls = set()
    seen_titles = set() # 用于防止同一篇文章在地方版和全国版重复出现
    
    # 执行 1: 抓取纯陕西地方频道 (放宽标题限制)
    print(" [1/2] 正在扫描各大央媒【陕西地方频道】...")
    for media_name, urls in LOCAL_CHANNELS.items():
        for url in urls:
            news = extract_news_from_url(media_name, url, date_patterns, is_local_channel=True)
            for w in news:
                if w["id"] not in seen_urls and w["title_hash"] not in seen_titles:
                    w["tags"] = analyze_news(w["text"])
                    final_results.append(w)
                    seen_urls.add(w["id"])
                    seen_titles.add(w["title_hash"])
                    print(f"    ✅ [收录] {w['media_std']} : {w['text'][:35]}...")
            time.sleep(1)
            
    # 执行 2: 抓取全国主频道 (严格执行陕西关键词限制)
    print("\n [2/2] 正在扫描各大央媒【全国主网频道】...")
    for media_name, urls in MAIN_CHANNELS.items():
        for url in urls:
            news = extract_news_from_url(media_name, url, date_patterns, is_local_channel=False)
            for w in news:
                if w["id"] not in seen_urls and w["title_hash"] not in seen_titles:
                    w["tags"] = analyze_news(w["text"])
                    final_results.append(w)
                    seen_urls.add(w["id"])
                    seen_titles.add(w["title_hash"])
                    print(f"    ✅ [收录] {w['media_std']} : {w['text'][:35]}...")
            time.sleep(1)
            
    print("=" * 60)
    print(f"📊 监测完成！共直接从服务器提取涉陕报道 {len(final_results)} 篇。")
    
    files = save_files(final_results, report_str)
    html = build_html_report(final_results, report_str)
    
    subject = f"🗞️ 央媒官网涉陕早报 ({report_str}) | 共抓取{len(final_results)}篇"
    if EMAIL_CONFIG["enabled"]: 
        send_email(subject, html, files)
    
if __name__ == "__main__":
    main()
