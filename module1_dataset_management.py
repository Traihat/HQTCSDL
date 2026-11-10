r"""
MODULE 1: TRAFFIC DATASET MANAGEMENT — XỬ LÝ FILE EXCEL / CSV (KỂ CẢ FILE LỚN HÀNG GB) & QUẢN LÝ DATABASE
===========================================================================================================
Thiết kế mới hoàn toàn cho dự án `8_LamLaiDuAn` theo đúng yêu cầu:
  - Phím chức năng xử lý dữ liệu trên thanh công cụ Web.
  - Kéo thả file dữ liệu vào ô `"Hay keo file du lieu cua ban vao o nay"` (nhận cả `.xlsx`, `.xls` và `.csv`, dung lượng tối đa 3 GB).
  - Hỗ trợ đọc phân luồng (Streaming Multi-Offset Chunking) cho các file `.csv` siêu lớn (như file UAV pNEUMA
    `20181029_dX_0830_0900.csv` nặng 1.72 GB) mà KHÔNG làm sập trình duyệt hay tràn RAM.
  - Tự động tiền xử lý làm sạch dữ liệu (lọc dòng trống, trùng lặp, xe đỗ tĩnh, ngoại lai vận tốc/gia tốc).
  - Tự động chia Khu vực (`DynamicZones`) và Khung giờ (`DynamicTimeFrames`) ĐỘNG 100% dựa trên dữ liệu nạp vào.
  - Sau khi tiền xử lý xong: nạp đầy đủ vào 9 bảng CSDL và in ra màn hình đúng 1 dòng thông báo xác nhận.
  - Có nút Xóa: xóa sạch database & dữ liệu cũ và hiển thị đúng thông báo:
    `"Da xoa thanh cong database va du lieu cu. San sang de nhan du lieu moi"`.
"""

import io
import hashlib
import math
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

_VENV_SITE = BASE_DIR.parent / "4_Code" / ".venv" / "Lib" / "site-packages"
if _VENV_SITE.exists() and sys.version_info[:2] == (3, 14) and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

try:
    import numpy as np
    import pandas as pd
except ImportError:
    for _py in (
        Path(r"C:\Users\taitr\AppData\Local\Programs\Python\Python314\python.exe"),
        BASE_DIR.parent / "4_Code" / ".venv" / "Scripts" / "python.exe",
    ):
        if _py.exists() and not os.environ.get("_UTA8_REEXEC"):
            _env = os.environ.copy()
            _env["_UTA8_REEXEC"] = "1"
            raise SystemExit(subprocess.call([str(_py), *sys.argv], env=_env))
    raise

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from db_manager import (
    DB_PATH,
    clear_all_database_data,
    find_dataset_by_checksum,
    get_connection,
    get_table_counts_df,
    init_db,
)
from module3_forecasting import run_forecasting_for_all_dynamic_zones
from module5_experiment_management import seed_default_experiments
from module6_reporting import seed_default_reports

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
UPLOAD_PROMPT_TEXT = "Hay keo file du lieu cua ban vao o nay"
DELETE_SUCCESS_TEXT = "Da xoa thanh cong database va du lieu cu. San sang de nhan du lieu moi"
PROCESS_SUCCESS_TEXT = "Đã xử lý dữ liệu và đưa dữ liệu vào database thành công!"
MAX_FILE_SIZE_KB = 3.0 * 1024.0 * 1024.0  # Giới hạn tối đa 3 GB (3,145,728 KB)
DEFAULT_STORAGE_ROOT = BASE_DIR / "storage" / "datasets"


class DuplicateDatasetError(ValueError):
    def __init__(self, dataset: dict) -> None:
        self.dataset = dataset
        super().__init__(f"File đã tồn tại dưới Dataset ID {dataset['dataset_id']}.")


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

