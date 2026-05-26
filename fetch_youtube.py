#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
未明シアター YouTube APIデータ取得スクリプト
============================================
このスクリプトは YouTube Data API / Analytics API からデータを取得し、
mimei_dashboard.html の実績値を自動更新します。

【初回実行】
  python fetch_youtube.py
  → ブラウザが開くので Google アカウントでログイン
  → 以降は token.json が保存されるため再ログイン不要

【毎日の使い方】
  python fetch_youtube.py          # 当月のデータを取得
  python fetch_youtube.py --all    # 全月分を再取得
"""

import os
import re
import sys
import json
import calendar
import argparse
import webbrowser
from datetime import datetime, date

# ── サードパーティライブラリ ──
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except ImportError:
    print("❌ 必要なライブラリが見つかりません。以下を実行してください:\n")
    print("   pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib\n")
    sys.exit(1)

# ── 設定 ──────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",          # 視聴回数/登録者など非収益メトリクス
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly", # 収益（要収益化）
]

CLIENT_SECRET_FILE = "client_secret.json"   # Google Cloud からダウンロードしたファイル
TOKEN_FILE         = "token.json"            # 認証後に自動生成
DASHBOARD_FILE     = "index.html"            # 更新対象の HTML

# 2026年度の月一覧 (年, 月) 順で 12ヶ月
FISCAL_MONTHS = [
    (2026, 4), (2026, 5), (2026, 6), (2026, 7), (2026, 8), (2026, 9),
    (2026, 10), (2026, 11), (2026, 12), (2027, 1), (2027, 2), (2027, 3),
]

# ── 認証 ─────────────────────────────────────────────
def get_credentials(force_reauth: bool = False):
    """OAuth 認証情報を取得（初回はブラウザが開く）"""
    creds = None

    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"❌ {CLIENT_SECRET_FILE} が見つかりません。")
        print("   Google Cloud Console で OAuth クライアント ID を作成し、")
        print(f"   このスクリプトと同じフォルダに {CLIENT_SECRET_FILE} として保存してください。\n")
        print("   詳細: https://console.cloud.google.com/apis/credentials")
        sys.exit(1)

    if force_reauth and os.path.exists(TOKEN_FILE):
        print("🔁 --reauth 指定: 既存の token.json を無視して再ログインします")
        try:
            os.remove(TOKEN_FILE)
        except Exception:
            pass

    if not force_reauth and os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 トークンを更新中...")
            creds.refresh(Request())
        else:
            print("🌐 ブラウザで Google アカウントにログインしてください...")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"✅ 認証完了。トークンを {TOKEN_FILE} に保存しました。\n")

    return creds


# ── YouTube Data API ──────────────────────────────────
def get_channel_id(youtube, debug=False):
    """自分のチャンネル ID を取得"""
    resp = youtube.channels().list(part="id,snippet,statistics", mine=True).execute()
    if not resp.get("items"):
        raise RuntimeError("チャンネルが見つかりません。")
    ch = resp["items"][0]
    print(f"📺 チャンネル: {ch['snippet']['title']} ({ch['id']})")
    if debug:
        stats = ch.get("statistics", {})
        print(f"  [DEBUG] 累計再生数: {stats.get('viewCount')}  登録者: {stats.get('subscriberCount')}  動画数: {stats.get('videoCount')}")
        print(f"  [DEBUG] 説明: {ch['snippet'].get('description','')[:120]!r}")
        print(f"  [DEBUG] カスタムURL: {ch['snippet'].get('customUrl')}")
    return ch["id"]


def get_videos_for_month(youtube, channel_id, year, month):
    """
    指定月に投稿された動画の (video_id, duration_seconds) リストを返す。
    60秒以下 → Shorts / それ以上 → 横動画 で判別。
    """
    last_day = calendar.monthrange(year, month)[1]
    published_after  = f"{year}-{month:02d}-01T00:00:00Z"
    published_before = f"{year}-{month:02d}-{last_day}T23:59:59Z"

    video_ids = []
    page_token = None

    # Search API で当月投稿動画を取得
    while True:
        resp = youtube.search().list(
            part="id",
            channelId=channel_id,
            publishedAfter=published_after,
            publishedBefore=published_before,
            type="video",
            maxResults=50,
            pageToken=page_token,
        ).execute()

        for item in resp.get("items", []):
            video_ids.append(item["id"]["videoId"])

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    if not video_ids:
        return [], []

    # Videos API で各動画の長さを取得（50件ずつ）
    shorts_ids = []
    horizontal_ids = []

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = youtube.videos().list(
            part="contentDetails",
            id=",".join(batch),
        ).execute()

        for v in resp.get("items", []):
            secs = parse_duration(v["contentDetails"]["duration"])
            if secs <= 60:
                shorts_ids.append(v["id"])
            else:
                horizontal_ids.append(v["id"])

    return horizontal_ids, shorts_ids


def parse_duration(iso_duration: str) -> int:
    """ISO 8601 duration (PT1M30S) → 秒数"""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + mi * 60 + s


# ── YouTube Analytics API ──────────────────────────────
def get_analytics_for_month(analytics, year, month, debug=False):
    """
    指定月のチャンネル全体の Analytics を取得。
    Returns: { revenue, total_views, subs_net }
    """
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year}-{month:02d}-01"
    end   = f"{year}-{month:02d}-{last_day}"

    try:
        resp = analytics.reports().query(
            ids="channel==MINE",
            startDate=start,
            endDate=end,
            metrics="estimatedRevenue,views,subscribersGained,subscribersLost",
            currency="JPY",
        ).execute()
    except Exception as e:
        if debug:
            print(f"\n  [DEBUG] Analytics API エラー ({year}-{month:02d}): {e}")
        else:
            print(f" Analytics エラー: {type(e).__name__}")
        return None

    if debug:
        import json as _json
        print(f"\n  [DEBUG] Analytics raw response ({year}-{month:02d}): {_json.dumps(resp, ensure_ascii=False)[:600]}")

    rows = resp.get("rows", [])
    if not rows:
        if debug:
            print(f"  [DEBUG] rows が空: ColumnHeaders={resp.get('columnHeaders')}")
        return None

    row = rows[0]
    subs_gained = int(row[2])
    subs_lost   = int(row[3])
    return {
        "revenue":     int(float(row[0])),   # JPY（currency="JPY" 指定済み）
        "total_views": int(row[1]),
        "subs_net":    subs_gained - subs_lost,  # 純増数（gained - lost）
    }


def get_views_by_content_type(analytics, year, month, debug=False):
    """
    チャンネル全体の再生数をコンテンツタイプ別（横動画 / ショート）に取得。
    過去動画の再生数も含む月間合計。
    Returns: (h_views, s_views)
    """
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year}-{month:02d}-01"
    end   = f"{year}-{month:02d}-{last_day}"

    try:
        resp = analytics.reports().query(
            ids="channel==MINE",
            startDate=start,
            endDate=end,
            dimensions="creatorContentType",
            metrics="views",
        ).execute()
    except Exception as e:
        if debug:
            print(f"\n  [DEBUG] creatorContentType エラー: {e}")
        return None, None

    if debug:
        import json as _json
        print(f"\n  [DEBUG] contentType response ({year}-{month:02d}): {_json.dumps(resp, ensure_ascii=False)[:400]}")

    h_views = 0
    s_views = 0
    for row in resp.get("rows", []):
        content_type = row[0]
        views = int(row[1])
        if content_type == "SHORTS":
            s_views = views
        else:
            # UPLOADED_VIDEO_LONG_FORM, VIDEO_LONG_FORM, LIVE_STREAM など横動画扱い
            h_views += views

    return h_views, s_views


# ── メイン処理 ────────────────────────────────────────
def fetch_month(youtube, analytics, channel_id, year, month, force=False, debug=False):
    """1ヶ月分のデータを取得して辞書で返す"""
    today = date.today()

    # 将来月はスキップ（当月は取得する、force なら全月取得）
    month_start = date(year, month, 1)
    if not force and month_start > today:
        return None

    print(f"  📅 {year}年{month}月 を取得中...", end=" ", flush=True)

    # Analytics（収益・合計再生数・純増登録者数）
    analytics_data = get_analytics_for_month(analytics, year, month, debug=debug)
    if not analytics_data:
        print("データなし")
        return None

    revenue     = analytics_data["revenue"]
    total_views = analytics_data["total_views"]
    subs        = analytics_data["subs_net"]   # 純増数（gained - lost）

    # コンテンツタイプ別再生数（チャンネル全体・過去動画含む）
    h_views, s_views = get_views_by_content_type(analytics, year, month, debug=debug)

    if h_views is None:
        # フォールバック: 合計再生数を横動画に割り当て
        h_views = total_views
        s_views = 0

    print(f"収益¥{revenue:,} / 横{h_views:,} / ショート{s_views:,} / 登録純増{subs:+,}")
    return {
        "revenue": revenue,
        "hview":   h_views,
        "sview":   s_views,
        "sub":     subs,
    }


def update_dashboard(actuals_dict: dict):
    """
    mimei_dashboard.html 内の ACTUALS オブジェクトを更新する。
    """
    if not os.path.exists(DASHBOARD_FILE):
        print(f"⚠️  {DASHBOARD_FILE} が見つかりません。同じフォルダに置いてください。")
        return

    with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    # ACTUALS = { ... }; の部分を置換
    pattern = r"(let ACTUALS\s*=\s*)\{[\s\S]*?\};"
    new_block = f"let ACTUALS = {json.dumps(actuals_dict, ensure_ascii=False, indent=2)};"

    if not re.search(pattern, html):
        print(f"⚠️  {DASHBOARD_FILE} 内に ACTUALS が見つかりません。手動で確認してください。")
        return

    new_html = re.sub(pattern, new_block, html)

    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"\n✅ {DASHBOARD_FILE} を更新しました！")


def main():
    parser = argparse.ArgumentParser(description="未明シアター YouTube データ取得")
    parser.add_argument("--all", action="store_true", help="全月分を強制再取得")
    parser.add_argument("--reauth", action="store_true", help="token.json を無視して再ログイン（別のYouTubeアカウントに切り替える時に使用）")
    parser.add_argument("--debug", action="store_true", help="API の生レスポンスや内部状態を表示")
    args = parser.parse_args()

    print("=" * 52)
    print("  未明シアター YouTube データ取得スクリプト")
    print("=" * 52)

    # 認証
    creds   = get_credentials(force_reauth=args.reauth)
    youtube  = build("youtube",          "v3",  credentials=creds)
    analytics = build("youtubeAnalytics", "v2", credentials=creds)

    # チャンネル ID 取得
    channel_id = get_channel_id(youtube, debug=args.debug)
    print()

    # 既存の ACTUALS を読み込む（差分更新のため）
    actuals = {
        "revenue": [None] * 12,
        "hview":   [None] * 12,
        "sview":   [None] * 12,
        "sub":     [None] * 12,
    }

    if os.path.exists(DASHBOARD_FILE):
        with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
            html = f.read()
        m = re.search(r"let ACTUALS\s*=\s*(\{[\s\S]*?\});", html)
        if m:
            try:
                actuals = json.loads(m.group(1))
            except Exception:
                pass

    # データ取得
    print("📊 データを取得しています...\n")
    for idx, (year, month) in enumerate(FISCAL_MONTHS):
        # --all 指定または値が null の月のみ取得（当月は常に再取得）
        today = date.today()
        is_current = (year == today.year and month == today.month)
        has_data   = actuals["revenue"][idx] not in (None, 0)

        if not args.all and has_data and not is_current:
            print(f"  📅 {year}年{month}月 スキップ（既存データあり）")
            continue

        result = fetch_month(youtube, analytics, channel_id, year, month, force=args.all, debug=args.debug)
        if result:
            actuals["revenue"][idx] = result["revenue"]
            actuals["hview"][idx]   = result["hview"]
            actuals["sview"][idx]   = result["sview"]
            actuals["sub"][idx]     = result["sub"]

    # HTML を更新
    print()
    update_dashboard(actuals)

    # ブラウザで開く
    dashboard_path = os.path.abspath(DASHBOARD_FILE)
    print(f"🌐 ダッシュボードを開きます: {dashboard_path}")
    webbrowser.open(f"file://{dashboard_path}")


if __name__ == "__main__":
    main()
