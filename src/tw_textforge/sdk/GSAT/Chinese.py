import os
import csv
from tw_textforge.agent.GSAT.chinese import GSATChineseGraph_QuestionAnalysis
from datasets import load_dataset
import pandas as pd
from functools import partial

def update_analysis(example, idx, checkpoint_analysis, write_col_name):
    if idx < len(checkpoint_analysis):
        example[write_col_name] = checkpoint_analysis[idx]
    return example

class GSAT_Chinese_QuestionAnalysis():
    """
    參數介紹:
    - dataset_name: 資料集名稱，預設為 "TsukiOwO/TW-GSAT-Chinese"
    - split: 資料集的分割，預設為 "train"
    - download_mode: 資料集下載模式，預設為 "force_redownload"(每次都強制重新下載)
    - generator_llm: 用於生成分析的 LLM，預設為 None，抓預設的 LLM
    - generator_llm_tools: 用於生成分析的 LLM 工具列表，預設為空列表
    - col_name: 用於存儲分析結果的列名，預設為 "analysis"
    - break_time: 每執行多少題目後暫停一次，預設為 10
    - save_dir: 儲存結果的目錄，預設為 "outputs/checkpoint"
    - csv_path: 儲存結果的 CSV 檔案路徑，預設為 "outputs/checkpoint/{dataset_name}.csv"
    """
    
    def __init__(self, dataset = None, dataset_name="TsukiOwO/TW-GSAT-Chinese", split="train", download_mode="force_redownload", generator_llm=None, generator_llm_tools=[], read_col_name = "text_pre_format", write_col_name = "analysis", break_time=10, interactive=True, test_mode=False):
        if dataset is not None:
            self.dataset = dataset
        else:
            self.dataset = load_dataset(dataset_name, split=split, download_mode=download_mode)
        self.dataset = self.dataset.add_column(write_col_name, [""] * len(self.dataset))
        self.chinese_graph = GSATChineseGraph_QuestionAnalysis(generator_llm=generator_llm, generator_llm_tools=generator_llm_tools)
        self.break_time = break_time
        self.safe_dataset_name = dataset_name.replace("/", "_")
        self.save_dir = "outputs/checkpoint"
        os.makedirs(self.save_dir, exist_ok=True)
        self.csv_path = os.path.join(self.save_dir, f"{self.safe_dataset_name}.csv")
        self.interactive = interactive
        self.test_mode = test_mode

        if os.path.exists(self.csv_path):
            with open(self.csv_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
                self.processed_count = len(rows) - 1 if len(rows) > 0 else 0  # 扣除 header
        else:
            self.processed_count = 0
        self.mode = "a" if os.path.exists(self.csv_path) else "w"
        self.first_run = self.processed_count == 0

        self.read_col_name = read_col_name
        self.write_col_name = write_col_name
        self.map_dataset = None
    
    def run(self):
        with open(self.csv_path, self.mode, newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if self.first_run:
                writer.writerow([self.write_col_name])  # col 0, row 0 是 header

            break_time = self.break_time
            total = len(self.dataset)
            print(f"總共需要執行的步驟量: {total}，已完成: {self.processed_count}")

            for idx in range(self.processed_count, total):

                print(f"當前執行步驟: {idx + 1}/{total}")
                response = self.chinese_graph.graph.invoke({
                    "messages": [
                        {"role": "user", "content": self.dataset[idx][self.read_col_name]}
                    ]
                })
                analysis = response["messages"][-1].content
                print(analysis)

                writer.writerow([analysis])
                f.flush()
                
                if self.interactive:
                    if (idx + 1) % break_time == 0 and idx != self.processed_count:
                        print(f"暫停題目: { idx + 2 }，等待輸入繼續或中止...")
                        if input("繼續請輸入 Y/y，輸入其他任意鍵中止: ").strip().lower() != "y":
                            print("結束執行。")
                            break
                elif self.test_mode:
                    break

    def checkpoint_mergeTo_datasets(self):
        checkpoint_df = pd.read_csv(self.csv_path)
        checkpoint_analysis = checkpoint_df[self.write_col_name].tolist()
        # 使用 functools.partial 函式，創建一個新的函式 `fn`，
        # 該函式是 `update_analysis` 的偏函式，預先綁定了 `checkpoint_analysis` 和 `write_col_name` 兩個參數。
        # 這樣在後續調用 `fn` 時，只需提供 `example` 和 `idx` 參數。
        fn = partial(update_analysis, checkpoint_analysis=checkpoint_analysis, write_col_name=self.write_col_name)
        self.map_dataset = self.dataset.map(fn, with_indices=True)
        return self.map_dataset

    
    def remove_checkpoint(self):
        if os.path.exists(self.csv_path):
            os.remove(self.csv_path)
            print(f"已刪除檢查點檔案: {self.csv_path}")
        else:
            print("檢查點檔案不存在。")