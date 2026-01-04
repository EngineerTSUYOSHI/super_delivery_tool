from datetime import datetime
import os
import sys

# 実行ファイルまたはスクリプトの場所
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# プロジェクトルート (srcの一階層上) 
ROOT_DIR = os.path.dirname(BASE_DIR) if not getattr(sys, "frozen", False) else BASE_DIR

# --- フォルダ構成の設定 ---
TMP_DIR = os.path.join(ROOT_DIR, "tmp")
TMP_CSV_DIR = os.path.join(TMP_DIR, "csv")
TMP_LOG_DIR = os.path.join(TMP_DIR, "log")
# --- パス関連の設定 ---
INPUT_FILE = os.path.join(ROOT_DIR, "input.xlsx")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"{datetime.now().strftime('%Y%m%d')}.xlsx")
SETTING_FILE = os.path.join(ROOT_DIR, "settings.txt")
AUTH_STATE_PATH = os.path.join(ROOT_DIR, "auth_state.json")


# --- 実行時の基本設定 ---
# 1ページあたりのURL収集数や上限
MAX_PAGES_PER_COMPANY = 10
# 中間保存を行う件数の目安（商品単位ではなく、結果の行数単位）
SAVE_INTERVAL = 100

# --- 待機時間の設定（秒） ---
WAIT_TIME_MIN = 2.0
WAIT_TIME_MAX = 5.0
WAIT_TIME_LOGIN = 5.0  # ログイン後の安定化待ち
WAIT_TIME_ERROR = 10.0  # エラー発生時の冷却時間
WAIT_TIME_MAINTENANCE = 20.0  # メンテナンス時の冷却時間
MAX_RETRIS = 3

# --- ブラウザ設定 ---
HEADLESS = True
# 画像を読み込まない設定にする場合はここを調整（現在はロジック側で制御想定）
SKIP_IMAGES = True
