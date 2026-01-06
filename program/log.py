"""
分級分流日誌模組 (log.py)

功能：將重複邏輯提取到核心函式中，實現 DRY 原則。
"""
from datetime import datetime
import traceback
import os
import sys
from typing import Optional

# --- 決定 Log 資料夾路徑 (始終寫入外部/可寫入位置) ---
if getattr(sys, 'frozen', False):
    # EXE 模式: 寫入 EXE 所在的資料夾 (例如 dist/)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 原始碼模式: 寫入專案根目錄 (program/ 的上一層)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOG_DIR = os.path.join(BASE_DIR, "log_files")


# --- 核心寫入邏輯 (私有函式) ---

def _write_log_core(
    sub_folder: str, 
    message: str, 
    trace_info: Optional[str] = None
):
    """
    核心寫入函式，處理檔案 I/O、路徑組合和 Traceback 邏輯。
    
    Args:
        sub_folder (str): 該 Log 寫入的子資料夾名稱 (如 "ERROR", "COMM")。
        message (str): 呼叫者傳入的自定義訊息。
        trace_info (str): 可選，完整的異常追蹤資訊。
    """
    
    # 1. 路徑組合與目錄創建
    category_dir = os.path.join(LOG_DIR, sub_folder)
    try:
        os.makedirs(category_dir, exist_ok=True)
    except OSError as e:
        print(f"無法建立日誌目錄 {category_dir}: {e}")
        return
    
    # 2. 檔案名稱與完整路徑
    today = datetime.now()
    file_name = today.strftime("%Y%m%d") + '.log'
    full_path = os.path.join(category_dir, file_name)

    # 3. 發生時間
    happen_time = today.strftime("%H:%M:%S.%f")[:-3]

    # 4. 建構日誌內容
    log_entry = f"[{happen_time}] [{sub_folder}]: {message}\n"
    
    # 5. 判斷是否需要加入 Traceback
    if trace_info and trace_info.strip():
        log_entry += f"--- TRACEBACK ---\n{trace_info}\n"
            
    # 6. 寫入日誌
    try:
        with open(full_path, 'a', encoding='utf-8') as fobj:
            fobj.write(log_entry)
    except Exception as write_e:
        print(f"致命錯誤：無法寫入日誌檔案 {full_path}: {write_e}")


# --- 對外部呼叫的 API 函式 (簡潔且功能明確) ---

def log_error_app(message: str ):
    """應用程式邏輯錯誤 (寫入 log_files/ERROR/)。自動捕捉 Traceback。"""
    # 這裡直接呼叫 traceback.format_exc()
    trace_info = traceback.format_exc()
    _write_log_core("ERROR", message, trace_info)


def log_comm(message: str):
    """網路/PLC 連線通訊紀錄 (寫入 log_files/COMM/)。自動捕捉 Traceback。"""
    # 這裡直接呼叫 traceback.format_exc()
    trace_info = traceback.format_exc()
    _write_log_core("COMM", message, trace_info)


def log_transaction(message: str, include_trace: bool = False):
    """
    正常的業務流程、交易步驟或 INFO 資訊 (寫入 INFO/)。
    :param message: 要記錄的訊息。
    :param include_trace: 是否在 Log 訊息中附加當前異常的 Traceback 資訊 (預設為 False)。
    """
    trace_info = None
    # 判斷開關是否開啟
    if include_trace:
        # 如果開啟，則呼叫 traceback.format_exc() 獲取資訊
        trace_info = traceback.format_exc()
    _write_log_core("INFO", message, trace_info)


# --- 測試區塊 ---
if __name__ == "__main__":
    print("--- Log 模組簡化版測試 ---")

    # 1. 測試 APP 錯誤紀錄 (發生於 except 區塊)
    try:
        result = 1 / 0
    except Exception as e:
        # 外部呼叫 log_error_app
        log_error_app(f"核心計算失敗: {e}")
        print("已記錄應用程式錯誤到 ERROR 子資料夾。")

    # 2. 測試 COMM 紀錄 (發生於 except 區塊)
    try:
        raise ConnectionRefusedError("PLC 連線被拒絕")
    except Exception as e:
        # 外部呼叫 log_comm
        log_comm(f"read_plc 嚴重連線失敗 | {e}")
        print("已記錄通訊失敗到 COMM 子資料夾。")
        
    # 3. 測試 INFO 紀錄 (不應有 Traceback)
    log_transaction("應用程式啟動，所有 Log 模組初始化成功。")
    print("已記錄交易流程到 INFO 子資料夾。")

    # 4. 擴展性示範：臨時將 INFO 級別設定為包含 Traceback (用於除錯)
    try:
        raise IndexError("測試異常")
    except Exception as e:
        log_transaction(f"緊急除錯模式下的 INFO 紀錄 | {e}",include_trace=True)

    
    print(f"\n測試完成。請檢查 {LOG_DIR} 資料夾。")