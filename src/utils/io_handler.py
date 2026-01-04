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
    """古いログを削除する

    :param log_dir: ログファイルが保存されているディレクトリ。
    :param days: 削除対象の古いログの基準日数。
    """
    now = time.time()
    files = glob.glob(os.path.join(log_dir, "*.log*"))
    for f in files:
        if os.stat(f).st_mtime < now - (days * 86400):
            logger.info(f"古いログを削除: {f}")
            os.remove(f)
