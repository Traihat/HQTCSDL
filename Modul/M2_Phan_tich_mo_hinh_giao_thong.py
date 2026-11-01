"""
MODULE 2 (M2): PHÂN TÍCH MÔ HÌNH GIAO THÔNG ĐÔ THỊ (TRAFFIC PATTERN ANALYSIS)
=============================================================================
Đáp ứng yêu cầu chức năng & câu hỏi nghiên cứu (RQ1, RQ4):
  - FR-13: Cho phép chọn vùng phân tích (6 vùng không gian) và khoảng gộp thời gian (10s, 15s, 30s, 60s).
  - FR-14: Tính số lượng xe, vận tốc trung bình, mật độ (xe/km) và lưu lượng dòng xe q = k * v (xe/giờ).
  - FR-15: Phát hiện và trích xuất các khung thời gian cao điểm (is_peak_period = 1).
  - FR-16: Nhận diện điểm nóng ùn tắc theo không gian (Spatial Hotspot Detection) trên lưới tọa độ (x, y).
  - FR-17: Phân loại và thống kê tỷ lệ % 4 mức độ ùn tắc (Free Flow, Moderate, Heavy, Gridlock).

Bảng CSDL tương tác (Phân hệ 2 & 3 - UrbanTrafficAnalyticsDB):
  - TrafficSpatialZones, TrafficAggregatedMetrics, Tracks, TrajectoryPoints
"""

import sqlite3
import sys
from pathlib import Path
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "database" / "UrbanTrafficAnalyticsDB.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Mở kết nối SQLite tới UrbanTrafficAnalyticsDB."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_available_zones_and_intervals(dataset_id: int = 1, db_path: Path = DB_PATH) -> dict:
    """FR-13: Lấy danh sách các vùng không gian và các khoảng gộp Δt hiện có trong CSDL."""
    conn = get_connection(db_path)
    zones_df = pd.read_sql(
        "SELECT zone_id, zone_name, x_min, x_max, y_min, y_max FROM TrafficSpatialZones WHERE dataset_id = ? ORDER BY zone_id",
        conn,
        params=(dataset_id,),
    )
    intervals_df = pd.read_sql(
        "SELECT DISTINCT window_interval_sec FROM TrafficAggregatedMetrics WHERE dataset_id = ? ORDER BY window_interval_sec",
        conn,
        params=(dataset_id,),
    )
    conn.close()
    return {
        "zones": zones_df,
        "intervals_sec": intervals_df["window_interval_sec"].astype(int).tolist(),
    }


def get_zone_timeseries(
    zone_name: str = "Khu_Trung_Tam",
    window_interval_sec: int = 30,
    dataset_id: int = 1,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    """
    FR-13 & FR-14: Truy vấn chuỗi thời gian chi tiết của một vùng và khoảng gộp Δt.
    Tính thêm đại lượng Lưu lượng dòng giao thông cơ bản: q = k * v (xe/giờ).
    """
    conn = get_connection(db_path)
    sql = """
    SELECT
        z.zone_name,
        m.window_interval_sec,
        m.window_start_time,
        m.window_end_time,
        m.vehicle_count,
        m.avg_speed_kmh,
        m.traffic_density_veh_km,
        ROUND(m.traffic_density_veh_km * m.avg_speed_kmh, 2) AS traffic_flow_veh_h,
        m.is_peak_period,
        m.congestion_level
    FROM TrafficAggregatedMetrics m
    JOIN TrafficSpatialZones z ON m.zone_id = z.zone_id
    WHERE m.dataset_id = ?
      AND z.zone_name = ?
      AND m.window_interval_sec = ?
    ORDER BY m.window_start_time
    """
    df = pd.read_sql(sql, conn, params=(dataset_id, zone_name, window_interval_sec))
    conn.close()
    return df


def summarize_traffic_by_zone(
    window_interval_sec: int = 30, dataset_id: int = 1, db_path: Path = DB_PATH
) -> pd.DataFrame:
    """
    FR-14: Thống kê tổng hợp số xe, vận tốc TB, mật độ TB/cực đại, lưu lượng TB (xe/giờ)
    và số khoảng cao điểm cho toàn bộ 6 khu vực.
    """
    conn = get_connection(db_path)
    sql = """
    SELECT
        z.zone_name AS Khu_Vuc,
        COUNT(m.metric_id) AS So_Khoang_Thoi_Gian,
        ROUND(AVG(m.vehicle_count), 2) AS So_Xe_TB,
        MAX(m.vehicle_count) AS So_Xe_Max,
        ROUND(AVG(m.avg_speed_kmh), 2) AS Van_Toc_TB_kmh,
        ROUND(AVG(m.traffic_density_veh_km), 2) AS Mat_Do_TB_xe_km,
        ROUND(MAX(m.traffic_density_veh_km), 2) AS Mat_Do_Max_xe_km,
        ROUND(AVG(m.traffic_density_veh_km * m.avg_speed_kmh), 2) AS Luu_Luong_TB_xe_gio,
        SUM(m.is_peak_period) AS So_Khoang_Cao_Diem
    FROM TrafficAggregatedMetrics m
    JOIN TrafficSpatialZones z ON m.zone_id = z.zone_id
    WHERE m.dataset_id = ? AND m.window_interval_sec = ?
    GROUP BY z.zone_name
    ORDER BY Mat_Do_TB_xe_km DESC
    """
    df = pd.read_sql(sql, conn, params=(dataset_id, window_interval_sec))
    conn.close()
    return df


def detect_peak_periods(
    zone_name: str = "Toan_Khu_Vuc",
    window_interval_sec: int = 30,
    top_n: int = 8,
    dataset_id: int = 1,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    """FR-15: Xác định Top khung thời gian cao điểm có mật độ phương tiện đông đúc nhất."""
    conn = get_connection(db_path)
    sql = """
    SELECT
        z.zone_name AS Khu_Vuc,
        substr(m.window_start_time, 12, 8) AS Bat_Dau,
        substr(m.window_end_time, 12, 8) AS Ket_Thuc,
        m.vehicle_count AS So_Xe,
        m.avg_speed_kmh AS Van_Toc_TB_kmh,
        m.traffic_density_veh_km AS Mat_Do_xe_km,
        ROUND(m.traffic_density_veh_km * m.avg_speed_kmh, 1) AS Luu_Luong_xe_gio,
        m.is_peak_period AS La_Cao_Diem,
        m.congestion_level AS Muc_Un_Tac
    FROM TrafficAggregatedMetrics m
    JOIN TrafficSpatialZones z ON m.zone_id = z.zone_id
    WHERE m.dataset_id = ?
      AND z.zone_name = ?
      AND m.window_interval_sec = ?
    ORDER BY m.traffic_density_veh_km DESC
    LIMIT ?
    """
    df = pd.read_sql(sql, conn, params=(dataset_id, zone_name, window_interval_sec, top_n))
    conn.close()
    return df


def analyze_congestion_distribution(
    window_interval_sec: int = 15, dataset_id: int = 1, db_path: Path = DB_PATH
) -> pd.DataFrame:
    """
    FR-17: Phân tích tỷ lệ phần trăm (%) 4 mức độ ùn tắc (Free Flow, Moderate, Heavy, Gridlock)
    theo từng nhánh và khu vực đô thị.
    """
    conn = get_connection(db_path)
    sql = """
    SELECT
        z.zone_name,
        m.congestion_level,
        COUNT(*) AS so_khoang
    FROM TrafficAggregatedMetrics m
    JOIN TrafficSpatialZones z ON m.zone_id = z.zone_id
    WHERE m.dataset_id = ?
      AND m.window_interval_sec = ?
      AND z.zone_name != 'Toan_Khu_Vuc'
    GROUP BY z.zone_name, m.congestion_level
    """
    df_raw = pd.read_sql(sql, conn, params=(dataset_id, window_interval_sec))
    conn.close()

    piv = (
        df_raw.pivot(index="zone_name", columns="congestion_level", values="so_khoang")
        .fillna(0)
        .reindex(columns=["Free Flow", "Moderate", "Heavy", "Gridlock"], fill_value=0)
    )
    piv_pct = piv.div(piv.sum(axis=1).replace(0, 1), axis=0).mul(100.0).round(1)
    piv_pct = piv_pct.reset_index().rename(columns={"zone_name": "Khu_Vuc"})
    return piv_pct


def identify_congestion_hotspots(
    grid_bins: int = 10, top_k: int = 6, dataset_id: int = 1, db_path: Path = DB_PATH
) -> pd.DataFrame:
    """
    FR-16: Nhận diện điểm nóng ùn tắc theo không gian (Spatial Hotspot Detection).
    Chia mặt phẳng tọa độ (x_pos, y_pos) của bảng TrajectoryPoints thành lưới ô chữ nhật,
    xếp hạng các ô có mật độ điểm xe tập trung cao đồng thời vận tốc trung bình thấp.
    """
    conn = get_connection(db_path)
    sql = """
    SELECT tp.x_pos, tp.y_pos, tp.speed_ms
    FROM TrajectoryPoints tp
    JOIN Tracks t ON tp.track_id = t.track_id
    WHERE t.dataset_id = ?
    """
    pts = pd.read_sql(sql, conn, params=(dataset_id,))
    zones = pd.read_sql(
        "SELECT zone_name, x_min, x_max, y_min, y_max FROM TrafficSpatialZones WHERE dataset_id = ? AND zone_name != 'Toan_Khu_Vuc'",
        conn,
        params=(dataset_id,),
    )
    conn.close()

    if pts.empty:
        return pd.DataFrame()

    pts["speed_kmh"] = pts["speed_ms"] * 3.6
    x_edges = np.linspace(float(pts["x_pos"].min()), float(pts["x_pos"].max()), grid_bins + 1)
    y_edges = np.linspace(float(pts["y_pos"].min()), float(pts["y_pos"].max()), grid_bins + 1)

    pts["gx"] = np.clip(np.digitize(pts["x_pos"], x_edges) - 1, 0, grid_bins - 1)
    pts["gy"] = np.clip(np.digitize(pts["y_pos"], y_edges) - 1, 0, grid_bins - 1)

    cell_stats = (
        pts.groupby(["gx", "gy"], as_index=False)
        .agg(
            so_diem_xe=("speed_kmh", "count"),
            van_toc_tb_kmh=("speed_kmh", "mean"),
            ty_le_di_cham_pct=("speed_kmh", lambda s: float((s < 10.0).mean() * 100.0)),
        )
    )
    # Chỉ xét các ô lưới có lượng phương tiện đáng kể (>= trung vị số điểm)
    min_pts = max(30, int(cell_stats["so_diem_xe"].median()))
    cell_stats = cell_stats[cell_stats["so_diem_xe"] >= min_pts].copy()

    # Chỉ số điểm nóng = Mật độ điểm chuẩn hóa * (1 + Tỷ lệ xe bò chậm < 10 km/h)
    cell_stats["hotspot_score"] = (
        (cell_stats["so_diem_xe"] / cell_stats["so_diem_xe"].max())
        * (1.0 + cell_stats["ty_le_di_cham_pct"] / 100.0)
    ).round(3)

    cell_stats["Toa_Do_X_m"] = cell_stats["gx"].apply(lambda i: f"[{x_edges[i]:.0f}, {x_edges[i+1]:.0f}]")
    cell_stats["Toa_Do_Y_m"] = cell_stats["gy"].apply(lambda j: f"[{y_edges[j]:.0f}, {y_edges[j+1]:.0f}]")
    cell_stats["tam_x"] = cell_stats["gx"].apply(lambda i: 0.5 * (x_edges[i] + x_edges[i + 1]))
    cell_stats["tam_y"] = cell_stats["gy"].apply(lambda j: 0.5 * (y_edges[j] + y_edges[j + 1]))

    def match_zone(row) -> str:
        for _, z in zones.iterrows():
            if z["x_min"] <= row["tam_x"] <= z["x_max"] and z["y_min"] <= row["tam_y"] <= z["y_max"]:
                return str(z["zone_name"])
        return "Vung_Ngoai_Bien"

    cell_stats["Thuoc_Khu_Vuc"] = cell_stats.apply(match_zone, axis=1)
    cell_stats["van_toc_tb_kmh"] = cell_stats["van_toc_tb_kmh"].round(2)
    cell_stats["ty_le_di_cham_pct"] = cell_stats["ty_le_di_cham_pct"].round(1)

    top_hotspots = (
        cell_stats.sort_values("hotspot_score", ascending=False)
        .head(top_k)
        .reset_index(drop=True)
    )
    top_hotspots.insert(0, "Hang_Hotspot", range(1, len(top_hotspots) + 1))
    return top_hotspots[
        [
            "Hang_Hotspot",
            "Thuoc_Khu_Vuc",
            "Toa_Do_X_m",
            "Toa_Do_Y_m",
            "so_diem_xe",
            "van_toc_tb_kmh",
            "ty_le_di_cham_pct",
            "hotspot_score",
        ]
    ]


def analyze_vehicle_composition(dataset_id: int = 1, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Thống kê số lượng và tỷ lệ % từng loại phương tiện cơ giới từ bảng Tracks."""
    conn = get_connection(db_path)
    df = pd.read_sql(
        """
        SELECT
            vehicle_type AS Loai_Phuong_Tien,
            COUNT(*) AS So_Luong_Xe,
            ROUND(AVG(total_frames) / 1.0, 1) AS So_Diem_TB_Moi_Xe
        FROM Tracks
        WHERE dataset_id = ?
        GROUP BY vehicle_type
        ORDER BY So_Luong_Xe DESC
        """,
        conn,
        params=(dataset_id,),
    )
    conn.close()
    total = max(int(df["So_Luong_Xe"].sum()), 1)
    df["Ty_Le_Pct"] = (df["So_Luong_Xe"] * 100.0 / total).round(2)
    return df


def run_demo() -> None:
    """Chạy kiểm thử độc lập toàn bộ chức năng phân tích của Module 2."""
    print("=" * 85)
    print("📊 MODULE 2 (M2): PHÂN TÍCH MÔ HÌNH GIAO THÔNG ĐÔ THỊ (Traffic Pattern Analysis)")
    print("=" * 85)

    meta = get_available_zones_and_intervals(dataset_id=1, db_path=DB_PATH)
    print(f"\n1️⃣ Các khoảng gộp thời gian hỗ trợ (FR-13): {meta['intervals_sec']} giây")
    print("   Danh sách 6 vùng không gian phân tích (TrafficSpatialZones):")
    print(meta["zones"].to_string(index=False))

    print("\n2️⃣ Cơ cấu 6 loại phương tiện cơ giới trong bảng Tracks:")
    print(analyze_vehicle_composition(dataset_id=1, db_path=DB_PATH).to_string(index=False))

    print("\n3️⃣ Bảng tổng hợp lưu lượng, vận tốc, mật độ theo từng khu vực (Δt = 30s - FR-14):")
    print(summarize_traffic_by_zone(window_interval_sec=30, dataset_id=1, db_path=DB_PATH).to_string(index=False))

    print("\n4️⃣ Top 6 khung giờ cao điểm đông đúc nhất Toàn khu vực (Δt = 30s - FR-15):")
    print(detect_peak_periods("Toan_Khu_Vuc", window_interval_sec=30, top_n=6, db_path=DB_PATH).to_string(index=False))

    print("\n5️⃣ Tỷ lệ phần trăm (%) 4 mức độ ùn tắc theo từng khu vực (Δt = 15s - FR-17):")
    print(analyze_congestion_distribution(window_interval_sec=15, db_path=DB_PATH).to_string(index=False))

    print("\n6️⃣ Top 6 Điểm nóng ùn tắc không gian (Spatial Hotspots) trên lưới tọa độ (x, y) (FR-16):")
    print(identify_congestion_hotspots(grid_bins=10, top_k=6, db_path=DB_PATH).to_string(index=False))


if __name__ == "__main__":
    run_demo()
