import csv
import glob
import logging
import os
import time
from typing import List, Dict

import pandas as pd

logger = logging.getLogger("SD_Scraper")


def save_to_csv_append(results: List[Dict[str, str]], csv_path: str) -> None:
    """データをCSVに追記保存する。

    100件ごとの中間保存に使用。

    :param results: 保存するデータのリスト。
    :param csv_path: 保存先のCSVファイルパス。
    """
    if not results:
        return

    file_exists = os.path.exists(csv_path)
    # Excelで開いても文字化けしないように utf-8-sig を採用
    with open(csv_path, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        if not file_exists:
            writer.writeheader()
        writer.writerows(results)


def convert_all_csv_to_excel(output_dir: str, output_excel: str) -> None:
    """ディレクトリ内のcsvを集約して一つのExcelにする。

    :param output_dir: CSVファイルが保存されているディレクトリ。
    :param output_excel: 出力先のExcelファイルパス。
    """
    logger.info("CSVをExcelに変換中...")

    csv_files = [f for f in os.listdir(output_dir) if f.endswith(".csv")]
    if not csv_files:
        logger.info("変換対象のCSVが見つかりませんでした。")
        return

    with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
        for csv_file in sorted(csv_files):
            comp_name = csv_file.replace("temp_", "").replace(".csv", "")
            # シート名の制約対応（31文字以内、禁止文字除去）
            sheet_name = "".join([c for c in comp_name if c not in r"/\\?*[]:"])[:31]

            csv_path = os.path.join(output_dir, csv_file)
            try:
                df = pd.read_csv(csv_path)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                logger.info(f"Sheet追加: {sheet_name}")
            except Exception as e:
                logger.error(f"Sheet追加に失敗しました： {csv_file}: {e}")


def prepare_output_dir(dir_path: str) -> None:
    """出力用ディレクトリが存在しない場合は作成する。

    :param dir_path: 作成するディレクトリのパス。
    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def remove_temp_csv(output_dir: str) -> None:
    """正常終了後に一時ファイルのcsvファイルをすべて削除する。

    :param output_dir: 削除対象のCSVファイルが保存されているディレクトリ。
    """
    temp_files = glob.glob(os.path.join(output_dir, "*.csv"))
    for f in temp_files:
        try:
            os.remove(f)
            logger.info("一時ファイルの削除完了。")
        except Exception as e:
            logger.error(f"一時ファイル {f} の削除に失敗しました: {e}")

def cleanup_old_logs(log_dir: str, days: int = 7) -> None:
    """古いファイルを名前や拡張子に関わらず全て削除する"""
    if not os.path.exists(log_dir):
        return

    now = time.time()
    cutoff = now - (days * 86400)
    
    # 全ファイルを取得
    files = glob.glob(os.path.join(log_dir, "*"))
    
    for f in files:
        # ディレクトリ（サブフォルダ）は念のため除外して、ファイルのみを対象にする
        if not os.path.isfile(f):
            continue

        # 最終更新日時がカットオフラインより前なら削除
        if os.stat(f).st_ctime < cutoff:
            try:
                os.remove(f)
                logger.info(f"古いファイルを削除しました: {os.path.basename(f)}")
            except Exception as e:
                # 使用中のファイル（今日のログなど）は削除できないので、エラーを無視または警告に留める
                logger.warning(f"ファイルの削除に失敗しました（使用中の可能性があります）: {os.path.basename(f)}")
