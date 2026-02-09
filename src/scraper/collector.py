import glob
import logging
import math
import os
import platform
import random
import re
import sys
import time
from typing import List, Dict, Optional

import config

logger = logging.getLogger("SD_Scraper")


class SuperDeliveryScraper:
    def __init__(self) -> None:
        """コンストラクタ"""
        self.login_url: str = "https://www.superdelivery.com/p/do/clickMemberLogin"
        self.pw: Optional[str] = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self, auth_state: Optional[str] = None, headless: bool = True) -> None:
        """ブラウザを起動する

        :param auth_state: 認証ファイルパス
        :param headless: ブラウザを表示するかのフラグ
        """
        from playwright.sync_api import sync_playwright

        logger.info("ブラウザの準備を開始します...")

        # パスを確認
        browser_path = self._get_executable_path()

        # なければインストールして再取得
        if not browser_path:
            if self._install_browser():
                browser_path = self._get_executable_path()

        if not browser_path:
            logger.error("ブラウザを特定・インストールできませんでした。終了します。")
            sys.exit(1)

        # 起動オプション
        launch_kwargs = {
            "headless": headless,
            "executable_path": browser_path,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        logger.info(f"ブラウザを起動します: {browser_path}")

        # Playwright起動
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(**launch_kwargs)

        # コンテキストとページの設定
        if auth_state and os.path.exists(auth_state):
            logger.info(f"認証情報を読み込みます: {auth_state}")
            self.context = self.browser.new_context(storage_state=auth_state)
        else:
            self.context = self.browser.new_context()

        self.page = self.context.new_page()

        # ボット対策
        self.page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => false});"
        )

    def login(self, user_id: str, password: str) -> bool:
        """ログインを実行する

        :param user_id: ログイン用ユーザID
        :param password: ログイン用パスワード

        :return: ログイン成功時はTrue、失敗時はFalse
        """
        try:
            logger.info("ログインを試みています...")
            self.page.goto(self.login_url)

            # IDとパスワードを入力（locatorを使ってスマートに）
            self.page.locator('input[name="identification"]').fill(user_id)
            self.page.locator('input[name="password"]').fill(password)

            # ログインボタンをクリック
            self.page.get_by_role("button", name="ログイン").click()

            # ログイン後の遷移を待つ
            self.page.wait_for_load_state("networkidle")

            # 成功判定：URLが変わったか、あるいは「ログアウト」ボタンが出現したかなどで判断
            if "login" in self.page.url:
                logger.info("Login failed.")
                return False
            return True

        except Exception as e:
            logger.error(f"An error occurred during login: {e}")
            return False

    def close(self) -> None:
        """ブラウザを閉じる"""
        if self.browser:
            self.browser.close()
        if self.pw:
            self.pw.stop()

    def get_max_pages(self, first_page_url: str) -> int:
        """商品一覧画面の最大ページ数を取得する

        :param first_page_url: 1ページ目のURL

        :return: 最大ページ数
        """
        self.page.goto(first_page_url)

        # 「（全28020件）」というテキストを探して数字だけ抜く
        total_text = self.page.locator(r"text=/（全\d+件）/").first.inner_text()
        # 正規表現で数字だけ取り出す
        total_count = int(re.search(r"\d+", total_text).group())

        # 1ページあたりの件数を取得（動的に取れるならベストだが、一旦120で固定）
        items_per_page = 120

        max_pages = math.ceil(total_count / items_per_page)
        logger.info(f"総件数: {total_count}件 -> 最大ページ数: {max_pages}")
        return max_pages

    def get_all_product_urls(
        self, base_url: str, start_page: int = 1, end_page: int = 10
    ) -> List[str]:
        """指摘したページ数までの商品一覧画面をスクレイピングし、全ての商品URLを取得する

        :param base_url: 1ページ目のURL（1ページ目のみURLが異なるため）
        :param start_page: URL取得開始ページ
        :param end_page: URL取得終了ページ

        :return: 商品詳細URLのリスト
        """
        # 1. サイト上の最大ページ数を取得
        site_max_pages = self.get_max_pages(base_url)

        # 2. 終了ページがサイトの最大値を超えないように制限
        actual_end_page = min(site_max_pages, end_page)

        # 開始ページが最大値を超えている場合のガード
        if start_page > actual_end_page:
            logger.warning(
                f"  [Warning] 開始ページ({start_page})が最大ページ数({actual_end_page})を超えています。"
            )
            return []

        logger.info(
            f"URL収集開始: {start_page} ページから {actual_end_page} ページまでを巡回します..."
        )

        all_product_urls = []

        for page_num in range(start_page, actual_end_page + 1):
            # 3. ページURLの生成
            if page_num == 1:
                # 1ページ目は基本URLそのまま
                current_url = base_url
            else:
                # 2ページ目以降はパスを調整
                parts = base_url.split("?")
                main_url = parts[0].rstrip("/")
                query = f"?{parts[1]}" if len(parts) > 1 else ""
                current_url = f"{main_url}/all/{page_num}/{query}"

            try:
                # 4. 1ページ分のURL取得
                page_urls = self.get_product_list(current_url)
                all_product_urls.extend(page_urls)

                logger.info(
                    f"Page {page_num}/{actual_end_page} 完了: +{len(page_urls)}件 (累計: {len(all_product_urls)}件)"
                )

                # 5. 負荷対策
                if page_num < actual_end_page:
                    time.sleep(random.uniform(1.0, 2.0))

            except Exception as e:
                logger.error(f"  [Error] Page {page_num} 取得失敗: {e}")
                continue

        logger.info(f"URL収集完了: 合計 {len(all_product_urls)} 件を取得しました。")
        return all_product_urls

    def get_product_list(self, list_url: str) -> List[str]:
        """一覧ページから商品URLを取得する

        :param list_url: 一覧ページのURL

        :return: 商品URLのリスト
        """
        logger.info(f"一覧ページに移動中: {list_url}")
        self.page.goto(list_url)

        # networkidleの代わりに、商品リンク（aタグ）が1つでも表示されるまで待つ
        try:
            self.page.wait_for_selector('a[href*="/p/r/pd_p/"]', timeout=10000)
        except Exception as e:
            logger.info("ページの読み込みに時間がかかっていますが、処理を続行します...")

        # 商品リンクを抽出
        # hrefの中に "/p/r/pd_p/" を含むaタグをすべて探す
        links = self.page.locator('a[href*="/p/r/pd_p/"]').all()

        urls = []
        for link in links:
            href = link.get_attribute("href")
            if href:
                # 重複を排除しながら絶対パスを作る
                full_url = (
                    f"https://www.superdelivery.com{href}"
                    if href.startswith("/")
                    else href
                )
                if full_url not in urls:
                    urls.append(full_url)

        logger.info(f"商品URLを {len(urls)} 件取得しました。")
        return urls

    def scrape_product_detail(self, url: str) -> List[Dict[str, str]]:
        """商品詳細情報をスクレイピングする

        :param url: 商品詳細ページのURL

        :return: 商品詳細情報の辞書
        """
        for attempt in range(config.MAX_RETRIS):
            try:
                # wait_until="domcontentloaded" で高速化
                self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # メンテナンス画面が出た場合の即時判定
                if "メンテナンス中" in self.page.content():
                    logger.warning(
                        f"制限検知。{config.WAIT_TIME_MAINTENANCE}秒待機してリトライします({attempt+1}/{config.MAX_RETRIS})"
                    )
                    time.sleep(config.WAIT_TIME_MAINTENANCE)
                    continue  # ループの先頭に戻ってリトライ

                # --- ここからが正常時の処理（ループを抜けるための成功ルート） ---

                # h1が出るまで待つ（これが通ればページが正常に表示されている証拠）
                try:
                    self.page.wait_for_selector("h1", timeout=15000)
                except Exception:
                    logger.warning(f"h1が見つかりません。リトライします。")
                    continue

                product_name = self.get_text_safe("h1")
                variation_results = []

                # 商品行の特定
                rows = self.page.locator("tr[data-product-set-code]").all()
                logger.info(f"抽出対象URL: {url}")

                for row in rows:
                    detail_cell = row.locator(".td-set-detail")
                    if detail_cell.count() == 0:
                        continue

                    name2_raw = detail_cell.inner_text().strip()

                    # JAN/型番抽出
                    jan_code = ""
                    jan_elem = detail_cell.locator(".td-jan")
                    if jan_elem.count() > 0:
                        jan_code = "".join(re.findall(r"\d+", jan_elem.inner_text()))

                    model_match = re.search(r"（(.*?)）", name2_raw)
                    model_number = model_match.group(1) if model_match else ""
                    name2 = name2_raw.split("（")[0].strip()

                    # --- 卸価格の取得（修正されたパス） ---
                    wholesale_price = "未取得"

                    # 行内、または直後の要素から価格を探す
                    # ログイン済みなら .td-price02 などのクラスがあるはず
                    price_locator = row.locator(
                        'xpath=./following-sibling::tr//td[contains(@class, "td-price02")] | .//span[contains(@class, "maker-wholesale-set-price")] | .//td[contains(@class, "td-price02")]'
                    ).first

                    if price_locator.count() > 0:
                        price_raw = price_locator.text_content()
                        price_match = re.search(r"([0-9,]+)", price_raw)
                        if price_match:
                            wholesale_price = price_match.group(1).replace(",", "")

                    variation_results.append(
                        {
                            "商品名": product_name,
                            "商品名2": name2,
                            "JANコード": jan_code,
                            "型番": model_number,
                            "価格": wholesale_price,
                            "詳細画面URL": url,
                        }
                    )
                return variation_results
            except Exception as e:
                logger.error(f"3回のリトライに失敗しました。: {e}")
                # ループの最後なら空を返して終了、そうでなければ次へ
                if attempt == config.MAX_RETRIS - 1:
                    return []
        return []  # すべての試行が失敗した場合

    def get_text_safe(self, selector: str) -> str:
        """テキストを安全に取得する

        :param selector: HTML要素のセレクタ

        :return: 取得したテキスト
        """
        try:
            element = self.page.locator(selector).first
            return element.inner_text().strip() if element.count() > 0 else ""
        except Exception:
            return ""

    def save_auth_state(self, file_path: str = "auth_state.json") -> None:
        """認証情報を保存する

        :param file_path: 保存するファイルパス
        """
        self.context.storage_state(path=file_path)
        logger.info("認証情報を保存しました")

    def _get_executable_path(self) -> Optional[str]:
        """ブラウザの実行ファイルパスを取得する

        :return: 実行ファイルパス。見つからない場合はNone
        """
        system = platform.system()
        base_dirs = []

        if system == "Windows":
            # 優先パス
            base_dirs.append("C:\\playwright-browsers")
            # 標準パス (LOCALAPPDATA)
            local_appdata = os.environ.get("LOCALAPPDATA")
            if local_appdata:
                base_dirs.append(os.path.join(local_appdata, "ms-playwright"))
            # USERPROFILE (念のため)
            user_profile = os.environ.get("USERPROFILE")
            if user_profile:
                base_dirs.append(os.path.join(user_profile, "AppData", "Local", "ms-playwright"))
        else:
            base_dirs.append(os.path.expanduser("~/Library/Caches/ms-playwright"))

        logger.info(f"ブラウザの検索を開始します (システム: {system})")
        for base in base_dirs:
            if not os.path.exists(base):
                continue

            logger.info(f"  検索中: {base}")
            if system == "Windows":
                # chrome-win か chrome-win64 のどちらかにある可能性が高い
                # より確実に探すために、再帰的に chrome.exe を探す
                pattern = os.path.join(base, "chromium-*", "**", "chrome.exe")
            else:
                pattern = os.path.join(
                    base, "chromium-*", "**", "Contents", "MacOS", "*"
                )

            candidates = glob.glob(pattern, recursive=True)
            for c in candidates:
                # headless_shell ではなく通常の chrome を優先
                if os.path.isfile(c) and "headless_shell" not in c:
                    return c
        
        logger.warning("ブラウザの実行ファイルが見つかりませんでした。")
        return None

    def _install_browser(self) -> bool:
        """ブラウザをインストールする

        :return: ブラウザのインストールに成功した場合はTrue、失敗した場合はFalse
        """
        logger.info("ブラウザが見つかりません。自動インストールを開始します...")
        try:
            original_argv = sys.argv
            
            # インストール先のパスを決定
            if platform.system() == "Windows":
                install_path = "C:\\playwright-browsers"
            else:
                install_path = os.path.expanduser("~/Library/Caches/ms-playwright")
            
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = install_path
            logger.info(f"インストール先: {install_path}")
            
            sys.argv = ["playwright", "install", "chromium"]

            import playwright
            from playwright.__main__ import main as playwright_main

            try:
                playwright_main()
            except SystemExit as e:
                # Playwrightがsys.exit()を呼んでも、ここで食い止める
                if e.code != 0:
                    logger.error(f"Playwrightのインストールコマンドがエラー終了しました (Exit Code: {e.code})")
                    raise
            finally:
                sys.argv = original_argv

            logger.info("ブラウザのインストールが完了しました。")
            time.sleep(1)
            return True
        except BaseException as e:
            logger.error(f"インストールの実行中に重大なエラーが発生しました: {e}")
            logger.error("手動でのインストールを試みてください：")
            logger.error("1. コマンドプロンプトを開く")
            if platform.system() == "Windows":
                logger.error(f"2. set PLAYWRIGHT_BROWSERS_PATH=C:\\playwright-browsers")
            logger.error(f"3. playwright install chromium")
            return False
