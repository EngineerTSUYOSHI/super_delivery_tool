import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from scraper.collector import SuperDeliveryScraper
import time
import cProfile
import pstats

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

def scrape_worker(url_list, auth_state_path):
    """1つのブラウザを立ち上げて、URLを順番に処理する"""
    print(f"起動中... {len(url_list)}件を順番に処理します")

    worker_scraper = SuperDeliveryScraper()
    # ログイン状態を読み込んでブラウザを起動
    worker_scraper.start(auth_state=auth_state_path)
    
    results = []
    for i, url in enumerate(url_list, start=1):
        try:
            # 1. 詳細情報を取得
            variations = worker_scraper.scrape_product_detail(url)
            if variations:
                results.extend(variations)
            
            # 2. 進捗を表示（1ワーカーだと順番に表示されるので見やすい）
            if i % 10 == 0:
                print(f"進捗: {i}/{len(url_list)} 件完了...")

        except Exception as e:
            print(f"Error at {url}: {e}")
            # エラー時も少し休む（連続エラーによる負荷を防ぐ）
            time.sleep(5)
            
    worker_scraper.close()
    return results


def main():
    # 1. 設定とパスの準備
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))    
    input_file = os.path.join(BASE_DIR, "input.xlsx")
    output_dir = os.path.join(BASE_DIR, "output")
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
            print(f"\n=== [詳細取得・直列] {comp_name} ===")
            
            with open(url_file, 'r', encoding='utf-8') as f:
                all_urls = [line.strip() for line in f if line.strip()]

            print(f"総件数: {len(all_urls)} 件の処理を開始します...")
            
            # 1ワーカー（直列）で実行。引数にリスト全体を渡す
            results = scrape_worker(all_urls, auth_state_path)
            
            # 取得した結果をExcel保存
            if results:
                save_to_excel_sheet(results, comp_name, output_file)
                print(f"-> {comp_name} のデータを保存しました。")
            
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
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        main()
    finally:
        profiler.disable()
        # バイナリ形式で保存（後で解析可能）
        profiler.dump_stats("profile_results.prof")
        
        # 同時にテキスト形式でも人間が見やすいように書き出す
        with open("profile_summary.txt", "w") as f:
            stats = pstats.Stats(profiler, stream=f).sort_stats('cumulative')
            stats.print_stats()
        print("プロファイル結果を保存しました（profile_results.prof / profile_summary.txt）")