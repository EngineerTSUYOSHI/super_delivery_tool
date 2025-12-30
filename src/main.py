import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from scraper.collector import SuperDeliveryScraper

# .envの読み込み
load_dotenv()

def main():
    # 1. 設定とパスの準備

    # 実行ファイル(main.py)の場所を基準に、プロジェクトのルート（親フォルダ）を特定する
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))    
    input_file = os.path.join(BASE_DIR, "input.xlsx")
    output_dir = os.path.join(BASE_DIR, "output")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_file = os.path.join(output_dir, f"output_{datetime.now().strftime('%Y%m%d')}.xlsx")
    
    user_id = os.getenv("SD_USER_ID")
    password = os.getenv("SD_PASSWORD")

    # 2. Excelの読み込み（ヘッダなし）
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return
        
    output_file = os.path.join(output_dir, f"output_{datetime.now().strftime('%Y%m%d')}.xlsx")

    # header=Noneで読み込み、列名を割り当てる
    df_input = pd.read_excel(input_file, header=None, names=["company_name", "url"])

    # 3. スクレイピング開始
    scraper = SuperDeliveryScraper()
    scraper.start()

    # if not scraper.login(user_id, password):
    #     print("Login failed. Exiting...")
    #     scraper.close()
    #     return

    try:
        for index, row in df_input.iterrows():
            company_name = row[0]
            base_url = row[1]

            # 会社ごとのURLリスト作成
            scraper.save_product_urls(company_name, base_url)
            
    finally:
        scraper.close()

    # 4. 会社ごとにループして結果を保存
    # ExcelWriterを使って複数シートに書き出す
    # with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    #     for index, row in df_input.iterrows():
    #         company = str(row["company_name"])
    #         url = row["url"]
            
    #         print(f"[{index + 1}/{len(df_input)}] Processing: {company}")
            
    #         # スクレイピング実行
    #         result_data = scraper.scrape_page(url)
            
    #         # 結果をDataFrameに変換（例として1行のデータ）
    #         # 実際には取得した項目に合わせて調整が必要だ
    #         df_result = pd.DataFrame([result_data])
            
    #         # Excelシート名用にサニタイズ（重要！）
    #         # / \ ? * [ ] : などの禁止文字を置換し、31文字以内に収める
    #         sheet_name = "".join([c for c in company if c not in r'/\?*[]:'])[:31]
            
    #         # シートに書き出し
    #         df_result.to_excel(writer, sheet_name=sheet_name, index=False)

    # scraper.close()
    # print(f"All process completed. Results saved to: {output_file}")

if __name__ == "__main__":
    main()