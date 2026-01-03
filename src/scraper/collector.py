import time
from playwright.sync_api import sync_playwright
import math
import re
import os
import random

class SuperDeliveryScraper:
    def __init__(self):
        self.login_url = "https://www.superdelivery.com/p/do/clickMemberLogin"
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self, auth_state=None):
        print("ブラウザを起動しています...")
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        if auth_state and os.path.exists(auth_state):
            print(f"認証情報を読み込んでいます: {auth_state}")
            self.context = self.browser.new_context(storage_state=auth_state)
        else:
            self.context = self.browser.new_context()

        self.page = self.context.new_page()

        # 外部ライブラリを使わず、直接「ボットじゃないよ」という証拠を刻む
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
        """)

    def login(self, user_id, password):
        try:
            print(f"Opening login page...")
            self.page.goto(self.login_url)

            # IDとパスワードを入力（locatorを使ってスマートに）
            self.page.locator('input[name="identification"]').fill(user_id)
            self.page.locator('input[name="password"]').fill(password)
            
            # ログインボタンをクリック
            self.page.get_by_role("button", name="ログイン").click()

            # ログイン後の遷移を待つ
            self.page.wait_for_load_state("networkidle")
            self.page.screenshot(path="after_login.png")
            
            # 成功判定：URLが変わったか、あるいは「ログアウト」ボタンが出現したかなどで判断
            if "login" in self.page.url:
                print("Login failed: Still on the login page.")
                return False
                
            print("Login successful.")
            return True

        except Exception as e:
            print(f"An error occurred during login: {e}")
            return False

    def scrape_page(self, url):
        """個別URLのスクレイピング。"""
        try:
            self.page.goto(url)
            self.page.wait_for_load_state("networkidle")
            
            # ここでデータを抽出する。
            # 例: タイトルを取得してみる
            title = self.page.title()
            
            # サーバーに負荷をかけすぎないよう、1秒ほど待機を入れるのがプロの作法だ
            time.sleep(1)
            
            return {"url": url, "title": title, "status": "Success"}
        except Exception as e:
            print(f"Failed to scrape {url}: {e}")
            return {"url": url, "status": "Error", "error": str(e)}

    def close(self):
        """リソースの解放。"""
        if self.browser:
            self.browser.close()
        if self.pw:
            self.pw.stop()

    def get_max_pages(self, first_page_url):
        self.page.goto(first_page_url)
        
        # 「（全28020件）」というテキストを探して数字だけ抜く
        total_text = total_text = self.page.locator(r'text=/（全\d+件）/').first.inner_text()
        # 正規表現で数字だけ取り出す
        total_count = int(re.search(r'\d+', total_text).group())
        
        # 1ページあたりの件数を取得（動的に取れるならベストだが、一旦120で固定）
        items_per_page = 120
        
        max_pages = math.ceil(total_count / items_per_page)
        print(f"総件数: {total_count}件 -> 最大ページ数: {max_pages}")
        return max_pages
    
    def save_product_urls(self, company_name, base_url):
        """全ページのURLを収集し、会社名ごとのテキストファイルに保存する"""
        max_pages = self.get_max_pages(base_url)
        if max_pages > 10:
            max_pages = 10  # テスト用に最大9ページまでに制限

        # 会社名ごとの保存ディレクトリ作成
        output_dir = f"data/urls/{company_name}"
        os.makedirs(output_dir, exist_ok=True)
        file_path = f"{output_dir}/product_urls.txt"
        
        print(f"【{company_name}】の収集開始: 全{max_pages}ページ")
        
        all_urls_count = 0
        with open(file_path, "w", encoding="utf-8") as f:
            for page_num in range(1, max_pages + 1):
                # ページURLの生成
                if page_num == 1:
                    current_url = base_url
                else:
                    parts = base_url.split('?')
                    main_url = parts[0].rstrip('/')
                    query = f"?{parts[1]}" if len(parts) > 1 else ""
                    current_url = f"{main_url}/all/{page_num}/{query}"
                
                # 1ページ分のURL取得
                page_urls = self.get_product_list(current_url)
                
                # ファイルに逐次書き込み（メモリ節約）
                for url in page_urls:
                    f.write(url + "\n")
                
                all_urls_count += len(page_urls)
                print(f"Page {page_num}/{max_pages} 完了: +{len(page_urls)}件 (累計: {all_urls_count}件)")
                
                # サーバー負荷対策
                time.sleep(1)
                
        print(f"【{company_name}】完了。{all_urls_count}件を保存しました: {file_path}")
        return file_path

    # 商品一覧ページで全商品のリンクを取得するイメージ
    def get_product_list(self, list_url):
        print(f"一覧ページに移動中: {list_url}")
        self.page.goto(list_url)
        
        # networkidleの代わりに、商品リンク（aタグ）が1つでも表示されるまで待つ
        # これならタイムアウトしにくい
        try:
            self.page.wait_for_selector('a[href*="/p/r/pd_p/"]', timeout=10000)
        except Exception as e:
            print("ページの読み込みに時間がかかっていますが、処理を続行します...")

        # 商品リンクを抽出
        # hrefの中に "/p/r/pd_p/" を含むaタグをすべて探す
        links = self.page.locator('a[href*="/p/r/pd_p/"]').all()
        
        urls = []
        for link in links:
            href = link.get_attribute('href')
            if href:
                # 重複を排除しながら絶対パスを作る
                full_url = f"https://www.superdelivery.com{href}" if href.startswith('/') else href
                if full_url not in urls:
                    urls.append(full_url)
                    
        print(f"商品URLを {len(urls)} 件取得しました。")
        return urls

    def get_text(self, selector):
        """要素が存在すればテキストを返し、なければNoneを返す補助関数"""
        try:
            element = self.page.locator(selector)
            if element.count() > 0:
                return element.first.inner_text().strip()
        except:
            pass
        return None
        
    def scrape_product_detail(self, url):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # wait_until="domcontentloaded" で高速化
                self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # メンテナンス画面が出た場合の即時判定
                if "メンテナンス中" in self.page.content():
                    wait_time = 20
                    print(f"      [Wait] 制限検知。{wait_time}秒待機してリトライします({attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    continue  # ループの先頭に戻ってリトライ
                self.page.screenshot(path="debug_no_data.png", full_page=True)
                
                # --- ここからが正常時の処理（ループを抜けるための成功ルート） ---
                
                # h1が出るまで待つ（これが通ればページが正常に表示されている証拠）
                try:
                    self.page.wait_for_selector('h1', timeout=15000)
                except:
                    print(f"      [Retry] h1が見つかりません。リトライします。")
                    continue

                product_name = self.get_text_safe('h1')
                variation_results = []

                # 商品行の特定
                rows = self.page.locator('tr[data-product-set-code]').all()
                print(f"    -> 抽出対象の行数: {len(rows)}")

                for row in rows:
                    detail_cell = row.locator('.td-set-detail')
                    if detail_cell.count() == 0:
                        continue

                    name2_raw = detail_cell.inner_text().strip()
                    
                    # JAN/型番抽出
                    jan_code = ""
                    jan_elem = detail_cell.locator('.td-jan')
                    if jan_elem.count() > 0:
                        jan_code = "".join(re.findall(r'\d+', jan_elem.inner_text()))

                    model_match = re.search(r'（(.*?)）', name2_raw)
                    model_number = model_match.group(1) if model_match else ""
                    name2 = name2_raw.split('（')[0].strip()

                    # --- 卸価格の取得（修正されたパス） ---
                    wholesale_price = "未取得"
                    
                    # 行内、または直後の要素から価格を探す
                    # ログイン済みなら .td-price02 などのクラスがあるはず
                    price_locator = row.locator('xpath=./following-sibling::tr//td[contains(@class, "td-price02")] | .//span[contains(@class, "maker-wholesale-set-price")] | .//td[contains(@class, "td-price02")]').first

                    if price_locator.count() > 0:
                        price_raw = price_locator.text_content()
                        price_match = re.search(r'([0-9,]+)', price_raw)
                        if price_match:
                            wholesale_price = price_match.group(1).replace(',', '')

                    variation_results.append({
                        "商品名": product_name,
                        "商品名2": name2,
                        "JANコード": jan_code,
                        "型番": model_number,
                        "価格": wholesale_price,
                        "詳細画面URL": url
                    })
                
                # すべて正常に終わったらランダム待機して結果を返却（ここで関数終了）
                time.sleep(random.uniform(2.0, 4.0))
                return variation_results

            except Exception as e:
                print(f"      [Error] Attempt {attempt+1} failed: {e}")
                time.sleep(5)
                # ループの最後なら空を返して終了、そうでなければ次へ
                if attempt == max_retries - 1:
                    return []
                    
        return [] # すべての試行が失敗した場合

    def get_text_safe(self, selector):
        try:
            element = self.page.locator(selector).first
            return element.inner_text().strip() if element.count() > 0 else ""
        except:
            return ""
        
    def save_auth_state(self, file_path="auth_state.json"):
        """ログイン状態をJSONファイルに保存する"""
        self.context.storage_state(path=file_path)
        print(f"Auth state saved to {file_path}")