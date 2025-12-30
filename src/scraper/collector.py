import time
from playwright.sync_api import sync_playwright, TimeoutError
from playwright_stealth import Stealth
import asyncio
import math
import re
import os

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

            print("ここで止まります。手動でログインボタンを押してみてください。")
            self.page.pause() # これを入れるとブラウザが一時停止し、デバッグツールが開く
            
            # ログインボタンをクリック
            self.page.get_by_role("button", name="ログイン").click()

            # ログイン後の遷移を待つ
            self.page.wait_for_load_state("networkidle")
            
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
        if max_pages > 5:
            max_pages = 5  # テスト用に最大5ページまでに制限
        
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
    
    def scrape_product_detail(self, url):
        try:
            self.page.goto(url)
            self.page.wait_for_load_state("networkidle")

            # 各項目の抽出（セレクタは実際のHTMLに合わせて調整が必要）
            data = {
                "商品名": self.get_text('.product-title'),
                "商品名2": self.get_text('.product-subtitle'), # 無ければ空
                "JANコード": self.get_text('.jan-code'),       # Null許容
                "型番": self.get_text('.model-number'),
                "価格": self.get_text('.retail-price'),        # とりあえず小売価格
                "詳細画面URL": url
            }
            return data
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
        
    def get_text(self, selector):
        """要素が存在すればテキストを返し、なければNoneを返す補助関数"""
        try:
            element = self.page.locator(selector)
            if element.count() > 0:
                return element.first.inner_text().strip()
        except:
            pass
        return None