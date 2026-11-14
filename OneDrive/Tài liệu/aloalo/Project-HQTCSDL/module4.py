"""
MODULE 4: VISUALIZATION DASHBOARD — BẢNG ĐIỀU KHIỂN TRỰC QUAN HÓA TỔNG HỢP (module4_visualization_dashboard.py)
=================================================================================================================
Thực hiện đầy đủ 100% các yêu cầu của Module 4 (`Visualization Dashboard`), mục `Traffic Visualization`
và mục `Dashboard` trong `1_nhu_cau_khach_hang.md`:
  1. Dashboard Summary:
     - KPIs (Tổng phương tiện sạch, Lưu lượng TB, Số vùng & khung giờ động)
     - Forecast accuracy (Độ chính xác dự báo tốt nhất 100% - MAPE, RMSE thấp nhất)
     - Peak periods (Khung giờ cao điểm toàn đô thị)
     - Congestion level (Trạng thái ùn tắc chủ đạo & tỷ lệ 4 mức độ)
     - Traffic statistics (Thống kê chi tiết toàn mạng lưới)
  2. 5 Nhóm Biểu đồ Tương tác (Interactive Charts):
     - Biểu đồ 1: Heatmap (Ma trận nhiệt Khu vực động × Khung giờ động & Mật độ không gian)
     - Biểu đồ 2: Traffic Trend Chart (Xu hướng lưu lượng xe/giờ & số lượng xe theo thời gian)
     - Biểu đồ 3: Density Chart (Biểu đồ mật độ giao thông xe/km qua các khu vực & thời gian)
     - Biểu đồ 4: Speed Chart (Biểu đồ vận tốc trung bình km/h & ngưỡng cảnh báo ùn tắc)
     - Biểu đồ 5: Distribution Chart & Forecast Visualization (Phân phối vận tốc Histogram,
                  Cơ cấu loại xe / mức ùn tắc & Tổng hợp dự báo ngắn hạn)
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


def get_module4_visualization_data(
    db_path: Path = DB_PATH,
    dataset_ids: list[int] | None = None,
) -> dict:
    """
    Trích xuất toàn bộ dữ liệu phục vụ Module 4 (Visualization Dashboard) trên Web.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    if dataset_ids:
        dataset_ids = list(dict.fromkeys(int(value) for value in dataset_ids))
        placeholders = ",".join("?" for _ in dataset_ids)
        imp_df = pd.read_sql(
            f"""
            SELECT * FROM DatasetImports
            WHERE import_id IN ({placeholders}) AND is_deleted = 0
              AND processing_status = 'saved'
            ORDER BY import_id DESC
            """,
            conn,
            params=dataset_ids,
        )
        if len(imp_df) != len(dataset_ids):
            conn.close()
            return {"has_data": False, "message": "Một hoặc nhiều Dataset không hợp lệ."}
    else:
        imp_df = pd.read_sql(
            """
            SELECT * FROM DatasetImports
            WHERE is_deleted = 0 AND processing_status = 'saved'
            ORDER BY import_id DESC LIMIT 1
            """,
            conn,
        )
    if imp_df.empty:
        conn.close()
        return {
            "has_data": False,
            "message": "Chưa có dữ liệu trong Database! Vui lòng vào Module 1 kéo thả file dữ liệu trước.",
        }

    selected_ids = imp_df["import_id"].astype(int).tolist()
    placeholders = ",".join("?" for _ in selected_ids)

    metrics_df = pd.read_sql(
        f"""
        SELECT
            m.*,
            z.zone_name,
            tf.timeframe_label
        FROM TrafficPatternMetrics m
        JOIN DynamicZones z ON m.zone_id = z.zone_id
        JOIN DynamicTimeFrames tf ON m.timeframe_id = tf.timeframe_id
        WHERE m.import_id IN ({placeholders})
        ORDER BY m.window_index ASC, m.zone_id ASC
        """,
        conn,
        params=selected_ids,
    )

    fc_df = pd.read_sql(
        f"""
        SELECT fc.*, z.zone_name
        FROM ForecastComparisons fc
        JOIN DynamicZones z ON fc.zone_id = z.zone_id
        WHERE fc.import_id IN ({placeholders})
        ORDER BY fc.zone_id ASC
        """,
        conn,
        params=selected_ids,
    )

    traj_df = pd.read_sql(
        f"""
        SELECT speed_kmh, vehicle_type, x_coord_m, y_coord_m
        FROM CleanedTrajectories
        WHERE import_id IN ({placeholders})
        """,
        conn,
        params=selected_ids,
    )
    conn.close()