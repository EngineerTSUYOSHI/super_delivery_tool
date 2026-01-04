import logging
import os
import sys
from datetime import datetime


def setup_logger(output_dir: str) -> logging.Logger:
    """コンソールとファイルの両方にログを出力する設定。

    :param output_dir: ログファイルを保存するディレクトリのパス。

    :return: 設定されたロガーオブジェクト。
    """
    logger = logging.getLogger("SD_Scraper")
    logger.setLevel(logging.INFO)

    # 既にハンドラがある場合は重複を避ける
    if logger.handlers:
        return logger

    # フォーマット設定 (日付 時刻 [レベル] メッセージ)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. コンソール出力用の設定
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. ファイル出力用の設定 (outputフォルダ内に保存)
    log_path = os.path.join(output_dir, datetime.now().strftime("%Y%m%d") + ".log")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
