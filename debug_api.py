#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YouTube Analytics API デバッグスクリプト"""

import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE = "token.json"
CLIENT_SECRET_FILE = "client_secret.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
]

creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())

analytics = build("youtubeAnalytics", "v2", credentials=creds)

# 5月のcreatorContentType別データを確認
print("=== 5月 creatorContentType ===")
resp = analytics.reports().query(
    ids="channel==MINE",
    startDate="2026-05-01",
    endDate="2026-05-31",
    dimensions="creatorContentType",
    metrics="views",
).execute()
print(json.dumps(resp, indent=2, ensure_ascii=False))

print("\n=== 4月 creatorContentType ===")
resp2 = analytics.reports().query(
    ids="channel==MINE",
    startDate="2026-04-01",
    endDate="2026-04-30",
    dimensions="creatorContentType",
    metrics="views",
).execute()
print(json.dumps(resp2, indent=2, ensure_ascii=False))
