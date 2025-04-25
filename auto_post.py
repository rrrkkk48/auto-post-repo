# Fixed indentation for Render deployment
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
from pymega import Mega

# ロガー（日本語あり、普段使い用）
logging.basicConfig(
    filename="log.txt",
    level=logging.INFO,
    format="%(asctime)s : %(message)s",
    filemode="w",
)

# インターネット接続を確認する関数
def check_internet_connection():
    try:
        # GoogleのDNSサーバーに接続確認する
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

# 環境変数のAPI_KEY情報等を取得
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

# 環境変数の値をロギング
logging.info(f"API_KEY: {API_KEY}")
logging.info(f"API_SECRET: {API_SECRET}")
logging.info(f"ACCESS_TOKEN: {ACCESS_TOKEN}")
logging.info(f"ACCESS_TOKEN_SECRET: {ACCESS_TOKEN_SECRET}")
logging.info(f"BEARER_TOKEN: {BEARER_TOKEN}")

# 環境変数が設定されていない場合のエラー
if not all(
    [API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, BEARER_TOKEN]
):
    raise ValueError(
        "環境変数が設定されていません。環境変数を設定してください。"
    )