import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from scraper.collector import SuperDeliveryScraper
from concurrent.futures import ProcessPoolExecutor
import time
import re

# .envの読み込み
load_dotenv()

def save_to_excel_sheet(results, company_name, output_file):
    """バッチ単位のリストを、指定した会社名のシートに追記・保存する"""
    # Excelシート名用にサニタイズ（禁止文字を除去し31文字以内）
    sheet_name = "".join([c for c in company_name if c not in r'/\?*[]:'])[:31]
    
    # ファイルが存在しない場合は新規作成
    if not os.path.exists(output_file):
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            pd.DataFrame().to_excel(writer, index=False)

    # 追記モードでExcelを開く
    with pd.ExcelWriter(output_file, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
        df = pd.DataFrame(results)
        
        # すでにそのシートがあるか確認し、開始行を決定
        start_row = 0
        header = True
        if sheet_name in writer.book.sheetnames:
            start_row = writer.book[sheet_name].max_row
            header = False # 追記時はヘッダー不要
            
        df.to_excel(writer, sheet_name=sheet_name, index=False, header=header, startrow=start_row)
    
    print(f"    -> [{sheet_name}] シートに {len(results)} 行を追記しました。")

def scrape_worker(url_chunk, worker_id, auth_state_path):
    """個別のブラウザを立ち上げて、割り当てられたURLを処理する"""
    print(f"    [Worker-{worker_id}] 起動中... {len(url_chunk)}件担当")
    
    worker_scraper = SuperDeliveryScraper()
    # 保存したログイン状態（auth_state.json）を読み込んでスタート
    worker_scraper.start(auth_state=auth_state_path)
    results = []
    for url in url_chunk:
        try:
            variations = worker_scraper.scrape_product_detail(url)
            if variations:
                results.extend(variations)
            time.sleep(1.5) # 並列時は少し長めに休む
        except Exception as e:
            print(f"    [Worker-{worker_id}] Error at {url}: {e}")
            
    worker_scraper.close()
    return results


def main():
    # 1. 設定とパスの準備
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))    
    input_file = os.path.join(BASE_DIR, "input.xlsx")
    output_dir = os.path.join(BASE_DIR, "output")
    url_data_dir = os.path.join(BASE_DIR, "data", "urls") # URLテキストの保存先
    auth_state_path = os.path.join(BASE_DIR, "src", "auth_state.json")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_file = os.path.join(output_dir, f"output_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
    
    # 2. Excelの読み込み
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    # A列:会社名, B列:URL (ヘッダなし)
    df_input = pd.read_excel(input_file, header=None)

    user_id = os.getenv("SD_USER_ID")
    password = os.getenv("SD_PASSWORD")
    # 3. スクレイピング開始
    master_scraper = SuperDeliveryScraper()
    master_scraper.start()
    if master_scraper.login(user_id, password):
        time.sleep(5)  # ログイン後の安定化待ち
        master_scraper.save_auth_state("auth_state.json")

    try:
        # --- ステップ1: 各会社の全商品URLをテキストに保存 ---
        company_tasks = []
        for index, row in df_input.iterrows():
            comp_name = str(row[0]).strip()
            b_url = str(row[1]).strip()
            
            print(f"\n=== [URL収集] {comp_name} ===")
            # collector.pyのsave_product_urlsを呼び出し（内部でファイル保存される）
            
            url_file_path = master_scraper.save_product_urls(comp_name, b_url)
            company_tasks.append((comp_name, url_file_path))
        master_scraper.close()

        # --- ステップ2: 保存したテキストを読み込んで詳細を取得 ---
        for comp_name, url_file in company_tasks:
            if not os.path.exists(url_file): continue
            print(f"\n=== [詳細取得・並列] {comp_name} ===")
            
            with open(url_file, 'r', encoding='utf-8') as f:
                all_urls = [line.strip() for line in f if line.strip()]

            # --- ここでURLリストを分割する！ ---
            num_workers = 4
            chunk_size = (len(all_urls) + num_workers - 1) // num_workers
            chunks = [all_urls[i:i + chunk_size] for i in range(0, len(all_urls), chunk_size)]

            # 1000件ずつとかではなく、分割した塊ごとに並列で投げる
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                # 2つのワーカーに、それぞれ分割したURLリストを渡す
                futures = []
                for idx, chunk in enumerate(chunks):
                    futures.append(executor.submit(scrape_worker, chunk, idx, auth_state_path))
                
                # 全ワーカーの結果を待機して結合
                combined_results = []
                for f in futures:
                    combined_results.extend(f.result())
                
                # まとめてExcel保存
                if combined_results:
                    save_to_excel_sheet(combined_results, comp_name, output_file)
            
    except Exception as e:
        print(f"致命的なエラーが発生しました: {e}")
    finally:
        if 'master_scraper' in locals():
            try:
                master_scraper.close()
            except:
                pass
        print(f"\n全工程が完了しました。出力先: {output_file}")

if __name__ == "__main__":
    main()