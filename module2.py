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
  def get_module2_dashboard_data(
    zone_id: str | int = "ALL",
    timeframe_id: str | int = "ALL",
    db_path: Path = DB_PATH,
    dataset_id: int | None = None,
    dataset_ids: list[int] | None = None,
) -> dict:
    """
    Truy vấn và tổng hợp toàn bộ chỉ số & biểu đồ của Module 2 theo đúng nút lọc
    Khu vực (`zone_id`) và Khung giờ (`timeframe_id`) mà người dùng đang bấm chọn trên Web.
    """
    if dataset_ids:
        dataset_ids = list(dict.fromkeys(int(value) for value in dataset_ids))
    elif dataset_id is not None:
        dataset_ids = [int(dataset_id)]
    filters_meta = get_dynamic_filters(db_path, dataset_id, dataset_ids)
    if not filters_meta["has_data"]:
        return {
            "has_data": False,
            "message": "Chưa có dữ liệu! Vui lòng vào Module 1 kéo thả file dữ liệu (.xlsx / .csv) để xử lý trước.",
        }

    conn = get_connection(db_path)
    if dataset_ids and len(filters_meta["imports"]) != len(dataset_ids):
        conn.close()
        return {
            "has_data": False,
            "message": "Một hoặc nhiều Dataset không tồn tại, đã lưu trữ hoặc chưa sẵn sàng.",
        }
    selected_dataset_id = int(filters_meta["import_info"]["import_id"])
    selected_ids = dataset_ids or [selected_dataset_id]
    placeholders = ",".join("?" for _ in selected_ids)
    where_clauses = [f"m.import_id IN ({placeholders})"]
    params: list = list(selected_ids)
    zone_code = None
    timeframe_code = None

    if str(zone_id).upper() != "ALL":
        zone_row = next(
            (row for row in filters_meta["zones"] if int(row["zone_id"]) == int(zone_id)),
            None,
        )
        if zone_row is None:
            conn.close()
            return {"has_data": True, "filters": filters_meta, "empty_filter": True}
        zone_code = zone_row["zone_code"]
        where_clauses.append("z.zone_code = ?")
        params.append(zone_code)
    if str(timeframe_id).upper() != "ALL":
        timeframe_row = next(
            (row for row in filters_meta["timeframes"] if int(row["timeframe_id"]) == int(timeframe_id)),
            None,
        )
        if timeframe_row is None:
            conn.close()
            return {"has_data": True, "filters": filters_meta, "empty_filter": True}
        timeframe_code = timeframe_row["timeframe_code"]
        where_clauses.append("tf.timeframe_code = ?")
        params.append(timeframe_code)

    where_sql = " AND ".join(where_clauses)

    metrics_df = pd.read_sql(
        f"""
        SELECT
            m.*,
            z.zone_code,
            z.zone_name,
            tf.timeframe_code,
            z.road_length_km,
            tf.timeframe_label
        FROM TrafficPatternMetrics m
        JOIN DynamicZones z ON m.zone_id = z.zone_id
        JOIN DynamicTimeFrames tf ON m.timeframe_id = tf.timeframe_id
        WHERE {where_sql}
        ORDER BY m.window_index ASC, m.zone_id ASC
        """,
        conn,
        params=params,
    )

    if metrics_df.empty:
        conn.close()
        return {
            "has_data": True,
            "filters": filters_meta,
            "selected_zone": str(zone_id),
            "selected_timeframe": str(timeframe_id),
            "empty_filter": True,
        }
    metrics_df["zone_id"] = metrics_df["zone_code"]
    metrics_df["timeframe_id"] = metrics_df["timeframe_code"]

    # 1. Tổng hợp thẻ KPI cho bộ lọc hiện tại
    total_veh = int(metrics_df["vehicle_count"].sum())
    car_cnt = int(metrics_df["car_count"].sum())
    moto_cnt = int(metrics_df["motorbike_count"].sum())
    bt_cnt = int(metrics_df["bus_truck_count"].sum())
    avg_speed = round(float(metrics_df["avg_speed_kmh"].mean()), 2)
    avg_density = round(float(metrics_df["traffic_density_veh_km"].mean()), 2)
    max_density = round(float(metrics_df["traffic_density_veh_km"].max()), 2)
    avg_flow = round(float(metrics_df["traffic_flow_veh_h"].mean()), 2)
    dom_cong = str(metrics_df["congestion_level"].mode().iloc[0])

    # 2. Phát hiện Khung giờ cao điểm (Peak-hour detection)
    peak_row = metrics_df.sort_values("traffic_density_veh_km", ascending=False).iloc[0]
    peak_info = {
        "window_time_label": str(peak_row["window_time_label"]),
        "timeframe_label": str(peak_row["timeframe_label"]),
        "zone_name": str(peak_row["zone_name"]),
        "peak_density_veh_km": round(float(peak_row["traffic_density_veh_km"]), 2),
        "peak_vehicles": int(peak_row["vehicle_count"]),
        "peak_speed_kmh": round(float(peak_row["avg_speed_kmh"]), 2),
    }

    # 3. Nhận diện Điểm nóng ùn tắc (Congestion hotspot identification)
    hotspot_df = metrics_df.sort_values("hotspot_score", ascending=False)
    top_hs = hotspot_df.iloc[0]
    top_hotspots_table = (
        hotspot_df[[
            "zone_name", "timeframe_label", "window_time_label",
            "hotspot_location", "vehicle_count", "avg_speed_kmh",
            "traffic_density_veh_km", "hotspot_score", "congestion_level",
        ]]
        .head(6)
        .to_dict(orient="records")
    )

    # 4. Chuỗi thời gian theo mốc window_time_label để vẽ biểu đồ trên Dashboard Module 2
    timeline_grp = (
        metrics_df.groupby(["window_index", "window_time_label"], as_index=False)
        .agg(
            vehicle_count=("vehicle_count", "sum"),
            avg_speed_kmh=("avg_speed_kmh", "mean"),
            traffic_density_veh_km=("traffic_density_veh_km", "mean"),
            traffic_flow_veh_h=("traffic_flow_veh_h", "mean"),
            is_peak_hour=("is_peak_hour", "max"),
        )
        .sort_values("window_index")
    )
    timeline_grp["avg_speed_kmh"] = timeline_grp["avg_speed_kmh"].round(2)
    timeline_grp["traffic_density_veh_km"] = timeline_grp["traffic_density_veh_km"].round(2)
    timeline_grp["traffic_flow_veh_h"] = timeline_grp["traffic_flow_veh_h"].round(2)
  
    # 5. Bảng tổng hợp theo từng Khu vực động trong bộ lọc hiện tại
    zone_grp = (
        metrics_df.groupby(["zone_id", "zone_name", "road_length_km"], as_index=False)
        .agg(
            total_vehicles=("vehicle_count", "sum"),
            avg_speed_kmh=("avg_speed_kmh", "mean"),
            avg_density_veh_km=("traffic_density_veh_km", "mean"),
            max_density_veh_km=("traffic_density_veh_km", "max"),
            avg_flow_veh_h=("traffic_flow_veh_h", "mean"),
            max_hotspot_score=("hotspot_score", "max"),
        )
        .sort_values("avg_density_veh_km", ascending=False)
    )
    for col in ("avg_speed_kmh", "avg_density_veh_km", "max_density_veh_km", "avg_flow_veh_h", "max_hotspot_score"):
        zone_grp[col] = zone_grp[col].round(2)

    # 6. Lấy mẫu điểm tọa độ không gian (x_coord_m, y_coord_m) của bộ lọc hiện tại để vẽ biểu đồ Không gian
    traj_where = [f"t.import_id IN ({placeholders})"]
    traj_params: list = list(selected_ids)
    if zone_code is not None:
        traj_where.append("z.zone_code = ?")
        traj_params.append(zone_code)
    if timeframe_code is not None:
        traj_where.append("tf.timeframe_code = ?")
        traj_params.append(timeframe_code)
    traj_df = pd.read_sql(
        f"""
        SELECT t.x_coord_m, t.y_coord_m, t.speed_kmh, t.vehicle_type, z.zone_name
        FROM CleanedTrajectories t
        JOIN DynamicZones z ON t.zone_id = z.zone_id
        JOIN DynamicTimeFrames tf ON t.timeframe_id = tf.timeframe_id
        WHERE {' AND '.join(traj_where)}
        LIMIT 600
        """,
        conn,
        params=traj_params,
    )
    conn.close()

    return {
        "has_data": True,
        "empty_filter": False,
        "filters": filters_meta,
        "selected_zone": str(zone_id),
        "selected_timeframe": str(timeframe_id),
        "kpis": {
            "total_vehicles": total_veh,
            "car_count": car_cnt,
            "motorbike_count": moto_cnt,
            "bus_truck_count": bt_cnt,
            "avg_speed_kmh": avg_speed,
            "avg_density_veh_km": avg_density,
            "max_density_veh_km": max_density,
            "avg_flow_veh_h": avg_flow,
            "dominant_congestion": dom_cong,
        },
        "peak_hour_detection": peak_info,
        "hotspot_identification": {
            "top_location": str(top_hs["hotspot_location"]),
            "top_score": round(float(top_hs["hotspot_score"]), 3),
            "top_congestion_level": str(top_hs["congestion_level"]),
            "hotspots_list": top_hotspots_table,
        },
        "timeline_series": timeline_grp.to_dict(orient="records"),
        "zone_breakdown": zone_grp.to_dict(orient="records"),
        "spatial_points": traj_df.to_dict(orient="records"),
        "selected_dataset_ids": selected_ids,
    }


