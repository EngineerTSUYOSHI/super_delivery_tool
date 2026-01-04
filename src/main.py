import os
# Playwrightがブラウザを探す場所を、システムの標準フォルダに固定する
# これがないと、PyInstallerの内部フォルダ（存在しない場所）を探してエラーになります
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
import random
import time

import pandas as pd
from dotenv import load_dotenv

import config
from scraper.collector import SuperDeliveryScraper
from utils import io_handler
from utils.logger import setup_logger

# .envの読み込み
load_dotenv(config.SETTING_FILE)
# ロガーのセットアップ
logger = setup_logger(config.TMP_LOG_DIR)

def main():
    # ファイル出力先のディレクトリ準備（念のため）
    io_handler.prepare_output_dir(config.OUTPUT_DIR)

    # ブラウザを開いてプログラム実行するかの判定
    headless = os.getenv("HEADLESS", "true").lower() == "true"
    # 初回はログインが必要なためauth_stateなしでブラウザ起動
    scraper = SuperDeliveryScraper()
    scraper.start(headless=headless)
    if scraper.login(os.getenv("USER_ID"), os.getenv("PASSWORD")):
        # ログイン後に安定するまで少し待機
        time.sleep(5)
        logger.info("ログインに成功しました。")
        # ログイン成功したら認証情報を保存
        scraper.save_auth_state(config.AUTH_STATE_PATH)
    else:
        logger.error("ログインに失敗しました。終了します。")
        scraper.close()
        return

    # inputファイルから会社名とURLを読み込む
    if not os.path.exists(config.INPUT_FILE):
        logger.error("入力ファイルが見つかりません。終了します。")
        return
    df_input = pd.read_excel(config.INPUT_FILE, header=None)

    # ターゲット企業リストを読み込む
    target_str = os.getenv("TARGET_COMPANIES", "")
    target_list = [t.strip() for t in target_str.split(",") if t.strip()]

    try:
        # inputファイルの会社毎にループ処理
        for _, row in df_input.iterrows():
            comp_name = str(row[0]).strip()
            b_url = str(row[1]).strip()
            # 特定の企業のみ絞りたい場合は企業名が合致しなければスキップする
            if target_list and comp_name not in target_list:
                logger.info(f"=== [スキップ] {comp_name} ===")
                continue
            temp_csv = os.path.join(config.TMP_CSV_DIR, f"{comp_name}.csv")

            logger.info(f"=== [処理開始] {comp_name} ===")
            logger.info(f"URLリストを作成中...")
            all_urls = scraper.get_all_product_urls(
                b_url,
                start_page=int(os.getenv("START_PAGE")),
                end_page=int(os.getenv("END_PAGE")),
            )
            logger.info(f"合計{len(all_urls)} 件のURLを検出しました。")

            # 1件ずつ詳細を取得し、100件ごとにCSVへ逃がす
            buffer = []
            for i, url in enumerate(all_urls, start=1):
                try:
                    variations = scraper.scrape_product_detail(url)
                    min_sleep = float(os.getenv("MIN_SLEEP", 2.0))
                    max_sleep = float(os.getenv("MAX_SLEEP", 4.0))
                    time.sleep(random.uniform(min_sleep, max_sleep))
                    if variations:
                        buffer.extend(variations)

                    if i % config.SAVE_INTERVAL == 0:
                        io_handler.save_to_csv_append(buffer, temp_csv)
                        buffer = []  # 書き込んだらメモリを空にする
                        logger.info(f"[中間保存] {i}件完了 (CSV追記済)")

                except Exception as e:
                    logger.error(f"{url}の処理中にエラー: {e}")
                    time.sleep(10)  # エラー時は長めに休む

            # 会社ごとの端数データを保存
            if buffer:
                io_handler.save_to_csv_append(buffer, temp_csv)
                logger.info(f"[完了] {comp_name}の全データをCSVに保存しました。")

        # 全社終了後にCSVをExcelに変換
        io_handler.convert_all_csv_to_excel(config.TMP_CSV_DIR, config.OUTPUT_FILE)
        io_handler.remove_temp_csv(config.TMP_CSV_DIR)
        io_handler.cleanup_old_logs(config.TMP_LOG_DIR)

    except Exception as e:
        logger.error(f"実行中に予期せぬエラーが発生しました: {e}")
    finally:
        if "master_scraper" in locals():
            scraper.close()
        logger.info(f"全工程が完了しました。最終出力: {config.OUTPUT_FILE}")


if __name__ == "__main__":
    main()
