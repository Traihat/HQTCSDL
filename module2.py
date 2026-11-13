"""
MODULE 2: TRAFFIC PATTERN ANALYSIS — PHÂN TÍCH GIAO THÔNG ĐỘNG THEO KHU VỰC & KHUNG GIỜ (module2_pattern_analysis.py)
=====================================================================================================================
  - Sau khi Module 1 thực hiện xong phần xử lý, khi ấn qua Module 2 sẽ in ra Dashboard.
  - Các nút lọc theo từng KHU VỰC và theo từng KHUNG GIỜ hoàn toàn ĐỘNG (không cố định),
    được lấy trực tiếp từ bảng `DynamicZones` và `DynamicTimeFrames` vừa sinh ra từ file nạp vào.
  - Tính toán đầy đủ các yêu cầu của Module 2 trong `1_nhu_cau_khach_hang.md`:
      1. Vehicle count analysis (Phân tích số lượng & cơ cấu phương tiện)
      2. Average speed analysis (Phân tích vận tốc trung bình)
      3. Traffic density & flow computation (Tính mật độ xe/km & lưu lượng xe/giờ)
      4. Peak-hour detection (Phát hiện khung giờ cao điểm)
      5. Congestion hotspot identification (Nhận diện điểm nóng ùn tắc)
      6. Spatial-temporal visualization (Dữ liệu trực quan hóa Không gian - Thời gian)
"""

import os
import subprocess
import sys
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

from db_manager import DB_PATH, get_connection, init_db


def get_dynamic_filters(
    db_path: Path = DB_PATH,
    dataset_id: int | None = None,
    dataset_ids: list[int] | None = None,
) -> dict:
    """
    Truy vấn danh sách các nút Khu vực động (`DynamicZones`) và Khung giờ động (`DynamicTimeFrames`)
    được sinh ra từ file dữ liệu vừa nạp ở Module 1.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    if dataset_ids:
        selected_ids = list(dict.fromkeys(int(value) for value in dataset_ids))
        placeholders = ",".join("?" for _ in selected_ids)
        imp_df = pd.read_sql(
            f"""
            SELECT * FROM DatasetImports
            WHERE import_id IN ({placeholders}) AND is_deleted = 0
              AND processing_status = 'saved'
            ORDER BY import_id DESC
            """,
            conn,
            params=selected_ids,
        )
    elif dataset_id is None:
        imp_df = pd.read_sql(
            """
            SELECT * FROM DatasetImports
            WHERE is_deleted = 0 AND processing_status = 'saved'
            ORDER BY import_id DESC LIMIT 1
            """,
            conn,
        )
    else:
        imp_df = pd.read_sql(
            """
            SELECT * FROM DatasetImports
            WHERE import_id = ? AND is_deleted = 0 AND processing_status = 'saved'
            """,
            conn,
            params=(int(dataset_id),),
        )
    if imp_df.empty:
        conn.close()
        return {"has_data": False, "zones": [], "timeframes": [], "import_info": None}

    selected_id = int(imp_df.iloc[0]["import_id"])
    zones_df = pd.read_sql(
        """
        SELECT zone_id, zone_code, zone_name, partition_method,
               x_min_m, x_max_m, y_min_m, y_max_m, road_length_km
        FROM DynamicZones
        WHERE import_id = ?
        ORDER BY zone_id ASC
        """,
        conn,
        params=(selected_id,),
    )
    tf_df = pd.read_sql(
        """
        SELECT timeframe_id, timeframe_code, timeframe_label,
               start_time_str, end_time_str, duration_minutes, is_peak_timeframe
        FROM DynamicTimeFrames
        WHERE import_id = ?
        ORDER BY timeframe_id ASC
        """,
        conn,
        params=(selected_id,),
    )
    conn.close()

    return {
        "has_data": True,
        "import_info": imp_df.iloc[0].to_dict(),
        "imports": imp_df.to_dict(orient="records"),
        "zones": zones_df.to_dict(orient="records"),
        "timeframes": tf_df.to_dict(orient="records"),
    }

