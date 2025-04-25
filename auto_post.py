import tweepy
import requests
from bs4 import BeautifulSoup
import random
import time
import schedule
import logging
import datetime
import urllib.parse
import os
import json
import socket

# ログ設定（1日分のみ、容量節約）
logging.basicConfig(filename='log.txt', level=logging.INFO, format='%(asctime)s: %(message)s', filemode='w')

# インターネット接続を確認する関数
def check_internet_connection():
    try:
        # GoogleのDNSサーバーに接続を試みる
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

# 環境変数からX API認証情報を取得
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

# 認証情報が設定されていない場合のエラーチェック
if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, BEARER_TOKEN]):
    logging.error("認証情報が設定されていません。環境変数を確認してください。")
    raise ValueError("認証情報が設定されていません。環境変数を確認してください。")

# Tweepyクライアント
client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

# 資格データをJSONファイルから読み込む
# クラウド環境（Heroku）でも動作するよう、相対パスを使用
QUALIFICATION_INFO = {}
try:
    # ローカル環境では C:/Users/rrkk/qualifications.json を使用
    # Herokuではルートディレクトリ（/app/）に配置される
    json_path = os.getenv("QUALIFICATIONS_PATH", "qualifications.json")
    with open(json_path, 'r', encoding='utf-8') as f:
        QUALIFICATION_INFO = json.load(f)
except Exception as e:
    logging.error(f"資格データの読み込みエラー: {e}")
    raise ValueError("資格データの読み込みに失敗しました。qualifications.jsonを確認してください。")

# 検索キーワード（資格名＋"最新 ニュース"）
QUALIFICATION_KEYWORDS = [f"{qual} 最新 ニュース" for qual in QUALIFICATION_INFO.keys()]

# 情報収集ソース（YouTubeを除外）
SOURCES = {
    "Google": "https://www.google.com/search?q={}",
    "Yahoo": "https://search.yahoo.co.jp/search?p={}",
    "X": lambda query: client.search_recent_tweets(query, max_results=10),
    "Instagram": "https://www.instagram.com/explore/tags/{}/",
    "TikTok": "https://www.tiktok.com/search?q={}"
}

def fetch_web_content(url):
    """Webページの内容を取得"""
    if not check_internet_connection():
        logging.error(f"インターネット接続がありません: {url}")
        return ""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logging.error(f"Web取得エラー: {url}, {e}")
        return ""

def scrape_titles(html, source):
    """HTMLからタイトルや説明を抽出"""
    try:
        soup = BeautifulSoup(html, 'html.parser')
        titles = []
        if source in ["Google", "Yahoo"]:
            for tag in ['h3', 'title', 'span', 'p']:
                elements = soup.find_all(tag)
                titles.extend([e.text.strip() for e in elements if e.text.strip()][:5])
                if titles:
                    break
        elif source in ["Instagram", "TikTok"]:
            titles = [p.text for p in soup.find_all(['p', 'span'])[:5]]
        return titles if titles else ["情報が見つかりませんでした"]
    except Exception as e:
        logging.error(f"スクレイピングエラー: {source}, {e}")
        return ["情報が見つかりませんでした"]

def fetch_x_tweets(query):
    """Xの投稿を検索"""
    if not check_internet_connection():
        logging.error(f"インターネット接続がありません: X検索, {query}")
        return ["インターネット接続がありません"]
    try:
        tweets = SOURCES["X"](query)
        if tweets.data:
            return [tweet.text for tweet in tweets.data if any(keyword in tweet.text for keyword in QUALIFICATION_KEYWORDS)][:3]
        return ["Xで情報が見つかりませんでした"]
    except tweepy.errors.TooManyRequests:
        logging.error(f"Xレート制限: {query}, 429 Too Many Requests")
        return ["Xレート制限のため情報取得不可"]
    except Exception as e:
        logging.error(f"X検索エラー: {query}, {e}")
        return ["Xで情報が見つかりませんでした"]

def collect_trending_info():
    """トレンド情報を収集"""
    if not check_internet_connection():
        logging.error("トレンド情報収集: インターネット接続がありません")
        return ["インターネット接続がありません"]
    
    trends = []
    keyword = random.choice(QUALIFICATION_KEYWORDS)
    logging.info(f"トレンド情報収集開始: キーワード={keyword}")
    
    for source, url in SOURCES.items():
        try:
            if source == "X":
                titles = fetch_x_tweets(keyword)
            else:
                encoded_keyword = urllib.parse.quote(keyword)
                html = fetch_web_content(url.format(encoded_keyword))
                titles = scrape_titles(html, source)
            logging.info(f"{source}から取得: {titles}")
            trends.extend(titles[:2])
            time.sleep(2)
        except Exception as e:
            logging.error(f"収集エラー: {source}, {e}")
    
    logging.info(f"収集されたトレンド: {trends}")
    if not trends or all("情報が見つかりませんでした" in t for t in trends):
        return ["資格試験の最新情報をチェック！"]
    return trends

def summarize_trend(trend):
    """トレンド情報を要約"""
    for qual in QUALIFICATION_INFO.keys():
        if qual in trend:
            return qual
    # トレンドに資格名が含まれない場合、ランダムに選択
    return random.choice(list(QUALIFICATION_INFO.keys()))

def create_post():
    """ポスト内容を生成"""
    trends = collect_trending_info()
    if not trends or "インターネット接続がありません" in trends:
        logging.info("トレンド情報が取得できませんでした")
        return None, None
    
    topic = summarize_trend(random.choice(trends))
    logging.info(f"選択されたトピック: {topic}")

    # 資格情報
    qual_info = QUALIFICATION_INFO.get(topic, QUALIFICATION_INFO[list(QUALIFICATION_INFO.keys())[0]])

    # 複数の文章テンプレート（丁寧語で統一）
    templates = [
        # テンプレート1: 試験概要と用途に焦点
        lambda q: (
            f"{q['topic']}はご存知ですか？\n\n"
            f"この資格は受験資格が{q['exam_qualification']}で、{q['exam_schedule']}に実施されます。試験形式は{q['exam_format']}です。\n"
            f"取得すれば{q['usage']}に役立ちます。",
            f"この{q['topic']}を取得することで、{q['usage']}の分野で活躍できます。\n"
            f"平均年収は{q['average_salary']}程度です。興味を持たれた方はぜひ挑戦してみてください。"
        ),
        # テンプレート2: 用途と年収に焦点
        lambda q: (
            f"おすすめの資格をご紹介します。\n\n"
            f"{q['topic']}を取得すると、{q['usage']}に役立つスキルが身につきます。\n"
            f"この分野の平均年収は{q['average_salary']}程度です。",
            f"試験は{q['exam_schedule']}に実施され、形式は{q['exam_format']}です。\n"
            f"受験資格は{q['exam_qualification']}なので、どなたでも挑戦できます。ぜひ検討してみてください。"
        ),
        # テンプレート3: 試験スケジュールと用途に焦点
        lambda q: (
            f"スキルアップを目指す方へ。\n\n"
            f"{q['topic']}は{q['exam_schedule']}に実施される試験です。\n"
            f"受験資格は{q['exam_qualification']}で、試験形式は{q['exam_format']}です。",
            f"この資格を取得すれば、{q['usage']}に役立つスキルが身につきます。\n"
            f"平均年収は{q['average_salary']}程度です。ぜひこの機会に挑戦してみてください。"
        ),
        # テンプレート4: 資格の魅力と用途
        lambda q: (
            f"キャリアアップに役立つ資格をご存知ですか？\n\n"
            f"{q['topic']}は{q['usage']}に役立つ資格です。\n"
            f"試験は{q['exam_schedule']}に実施されます。",
            f"試験形式は{q['exam_format']}で、受験資格は{q['exam_qualification']}です。\n"
            f"平均年収は{q['average_salary']}程度です。新しいスキルを身につけるチャンスです。"
        ),
        # テンプレート5: 年収と試験概要
        lambda q: (
            f"高収入を目指すならこの資格はいかがですか？\n\n"
            f"{q['topic']}の平均年収は{q['average_salary']}程度です。\n"
            f"試験は{q['exam_schedule']}に実施されます。",
            f"試験形式は{q['exam_format']}で、受験資格は{q['exam_qualification']}です。\n"
            f"取得すれば{q['usage']}に役立つスキルが身につきます。ぜひ挑戦してみてください。"
        ),
        # テンプレート6: 用途と受験資格
        lambda q: (
            f"新しいキャリアを考える方へ。\n\n"
            f"{q['topic']}は{q['usage']}に役立つ資格です。\n"
            f"受験資格は{q['exam_qualification']}なので挑戦しやすいです。",
            f"試験は{q['exam_schedule']}に実施され、形式は{q['exam_format']}です。\n"
            f"平均年収は{q['average_salary']}程度です。スキルアップの第一歩としておすすめです。"
        ),
        # テンプレート7: 試験形式と用途
        lambda q: (
            f"資格取得で未来を切り開きませんか？\n\n"
            f"{q['topic']}の試験形式は{q['exam_format']}です。\n"
            f"取得すれば{q['usage']}に役立つスキルが身につきます。",
            f"試験は{q['exam_schedule']}に実施されます。\n"
            f"受験資格は{q['exam_qualification']}で、平均年収は{q['average_salary']}程度です。ぜひご検討ください。"
        ),
        # テンプレート8: スケジュールと年収
        lambda q: (
            f"資格取得のチャンスがやってきます。\n\n"
            f"{q['topic']}は{q['exam_schedule']}に実施される試験です。\n"
            f"平均年収は{q['average_salary']}程度です。",
            f"試験形式は{q['exam_format']}で、受験資格は{q['exam_qualification']}です。\n"
            f"取得すれば{q['usage']}に役立つスキルが身につきます。ぜひ挑戦してみてください。"
        ),
        # テンプレート9: 用途と試験スケジュール
        lambda q: (
            f"将来に役立つ資格をお探しの方へ。\n\n"
            f"{q['topic']}は{q['usage']}に役立つ資格です。\n"
            f"試験は{q['exam_schedule']}に実施されます。",
            f"試験形式は{q['exam_format']}で、受験資格は{q['exam_qualification']}です。\n"
            f"平均年収は{q['average_salary']}程度です。新しい一歩を踏み出すきっかけになります。"
        ),
        # テンプレート10: 受験資格と年収
        lambda q: (
            f"誰でも挑戦できる資格をご紹介します。\n\n"
            f"{q['topic']}の受験資格は{q['exam_qualification']}です。\n"
            f"平均年収は{q['average_salary']}程度です。",
            f"試験は{q['exam_schedule']}に実施され、形式は{q['exam_format']}です。\n"
            f"取得すれば{q['usage']}に役立つスキルが身につきます。ぜひチェックしてみてください。"
        ),
        # テンプレート11: 試験概要と年収
        lambda q: (
            f"スキルアップを目指すならこの資格がおすすめです。\n\n"
            f"{q['topic']}は{q['exam_schedule']}に実施される試験です。\n"
            f"平均年収は{q['average_salary']}程度です。",
            f"試験形式は{q['exam_format']}で、受験資格は{q['exam_qualification']}です。\n"
            f"取得すれば{q['usage']}に役立つスキルが身につきます。ぜひ挑戦してみてください。"
        ),
        # テンプレート12: 用途と試験形式
        lambda q: (
            f"新しいスキルを身につけたい方へ。\n\n"
            f"{q['topic']}は{q['usage']}に役立つ資格です。\n"
            f"試験形式は{q['exam_format']}です。",
            f"試験は{q['exam_schedule']}に実施されます。\n"
            f"受験資格は{q['exam_qualification']}で、平均年収は{q['average_salary']}程度です。興味のある方はぜひご検討ください。"
        ),
        # テンプレート13: 総合的な紹介
        lambda q: (
            f"おすすめの資格をご紹介します。\n\n"
            f"{q['topic']}は{q['exam_schedule']}に実施される試験です。\n"
            f"取得すれば{q['usage']}に役立ちます。",
            f"試験形式は{q['exam_format']}、受験資格は{q['exam_qualification']}です。\n"
            f"平均年収は{q['average_salary']}程度です。スキルアップを目指す方はぜひ挑戦してください。"
        )
    ]

    # ランダムにテンプレートを選択
    selected_template = random.choice(templates)
    main_content, reply_content = selected_template({
        "topic": topic,
        "exam_qualification": qual_info["exam_qualification"],
        "exam_schedule": qual_info["exam_schedule"],
        "exam_format": qual_info["exam_format"],
        "usage": qual_info["usage"],
        "average_salary": qual_info["average_salary"]
    })

    # メインのポスト（120～139文字）
    main_post = main_content
    if len(main_post) > 139:
        # 139文字以内に収まるように調整し、文の途中で終わらないようにする
        sentences = main_post.split("。")
        main_post = ""
        for sentence in sentences:
            if not sentence:
                continue
            # 次の文を追加しても139文字を超えない場合のみ追加
            temp = (main_post + sentence + "。").strip()
            if len(temp) <= 139:
                main_post = temp
            else:
                break
        # 最後の「。」がない場合に追加
        if main_post and not main_post.endswith("。"):
            main_post += "。"
    elif len(main_post) < 120:
        main_post += "\n詳細はリプライでご確認ください。"

    # リプライ（139文字以内）
    reply_post = reply_content
    if len(reply_post) > 139:
        reply_post = reply_post[:136] + "..."

    logging.info(f"メインのポスト: {main_post}, 長さ: {len(main_post)}")
    if reply_post:
        logging.info(f"リプライのポスト: {reply_post}, 長さ: {len(reply_post)}")

    return main_post, reply_post

def post_to_x():
    """Xにポスト"""
    if not check_internet_connection():
        logging.error("投稿: インターネット接続がありません")
        return
    
    main_post, reply_post = create_post()
    if not main_post:
        logging.info("ポスト生成失敗、スキップ")
        return
    
    try:
        # メインのポストを投稿
        main_tweet = client.create_tweet(text=main_post)
        logging.info(f"メインのポスト成功: {main_post}")
        
        # リプライがある場合
        if reply_post:
            client.create_tweet(text=reply_post, in_reply_to_tweet_id=main_tweet.data['id'])
            logging.info(f"リプライのポスト成功: {reply_post}")
    except Exception as e:
        logging.error(f"ポストエラー: {e}")

def schedule_posts():
    """1日7ポストをスケジュール"""
    logging.info("スケジュール設定開始")
    
    patterns = {
        "A": ["07:22", "08:00", "11:00", "15:00", "17:00", "20:00", "23:00"],
        "B": ["07:22", "09:00", "12:00", "15:30", "18:20", "20:30", "23:30"],
        "C": ["07:22", "07:30", "13:00", "16:20", "18:40", "20:45", "22:20"]
    }
    
    selected_pattern = random.choice(list(patterns.keys()))
    logging.info(f"選択されたパターン: {selected_pattern}")
    
    for time_str in patterns[selected_pattern]:
        schedule.every().day.at(time_str).do(post_to_x)
        logging.info(f"スケジュール時刻: {time_str}")
    
    logging.info("スケジュール設定完了")

if __name__ == "__main__":
    logging.info("自動ポストプログラム開始")
    schedule_posts()
    
    while True:
        now = datetime.datetime.now()
        if now.day == 1 and now.hour == 0:
            logging.info("月初リセット")
            schedule.clear()
            schedule_posts()
        
        schedule.run_pending()
        time.sleep(60)