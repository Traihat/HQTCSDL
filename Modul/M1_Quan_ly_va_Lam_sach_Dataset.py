"""
MODULE 1 (M1): QUẢN LÝ TẬP DỮ LIỆU & KIỂM TRA CHẤT LƯỢNG / LÀM SẠCH QUỸ ĐẠO UAV
================================================================================
Đáp ứng yêu cầu chức năng & câu hỏi nghiên cứu (RQ1):
  - FR-04, FR-10: Đăng ký tập dữ liệu quỹ đạo UAV (pNEUMA / inD) kèm đầy đủ metadata.
  - FR-05: Xem trước N dòng đầu và thống kê cơ bản của file dữ liệu.
  - FR-06, FR-39: Kiểm tra schema cột bắt buộc & kiểu dữ liệu, chỉ rõ dòng/cột lỗi.
  - FR-07: Quản lý phiên bản dataset (tự động nâng version_tag, không ghi đè bản cũ).
  - FR-08, FR-09: Lưu trữ (Archive) và Xóa dataset (chặn xóa nếu đã có Experiments tham chiếu).
  - FR-11, FR-12: Làm sạch 4 bước (thiếu/trùng, xe đỗ tĩnh, ngoại lai vận tốc/gia tốc,
                  quỹ đạo quá ngắn), chuẩn hóa tọa độ mét (x_pos, y_pos) và sinh Báo cáo chất lượng.

Bảng CSDL tương tác (Phân hệ 2 & 3 - UrbanTrafficAnalyticsDB):
  - Datasets, Tracks, TrajectoryPoints, TrafficSpatialZones, TrafficAggregatedMetrics, AuditLogs
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
DEFAULT_UAV_CSV = BASE_DIR / "Tuan_02_04_Xu_ly_du_lieu_UAV" / "20181029_dX_0830_0900.csv"

REQUIRED_PNEUMA_COLS = [
    "track_id", "type", "traveled_d", "avg_speed",
    "lat", "lon", "speed", "lon_acc", "lat_acc", "time",
]

# Định nghĩa 6 vùng không gian chuẩn (zone_name, x_min, x_max, y_min, y_max, chiều dài đường km)
ZONES_DEF = [
    ("Khu_Trung_Tam", 450.0,  900.0,  650.0, 1400.0, 1.50),
    ("Nhanh_Bac",     300.0, 1000.0, 1400.0, 1900.0, 1.00),
    ("Nhanh_Nam",     300.0, 1000.0,    0.0,  650.0, 1.00),
    ("Nhanh_Tay",       0.0,  450.0,  500.0, 1500.0, 0.90),
    ("Nhanh_Dong",    900.0, 1315.0,  500.0, 1500.0, 0.90),
    ("Toan_Khu_Vuc",    0.0, 1315.0,    0.0, 1900.0, 5.30),
]


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Mở kết nối SQLite tới UrbanTrafficAnalyticsDB và bật khóa ngoại."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def list_datasets(include_archived: bool = False, db_path: Path = DB_PATH) -> pd.DataFrame:
    """FR-07, FR-09, FR-10: Liệt kê các phiên bản Dataset (mặc định ẩn các bản đã Archived)."""
    conn = get_connection(db_path)
    where_clause = "" if include_archived else "WHERE d.status != 'Archived'"
    sql = f"""
    SELECT
        d.dataset_id,
        d.name,
        d.source_type,
        d.version_tag,
        d.location_name,
        d.frame_rate_hz,
        d.status,
        COALESCE(u.username, 'N/A') AS nguoi_tai_len,
        (SELECT COUNT(*) FROM Tracks t WHERE t.dataset_id = d.dataset_id) AS so_xe_tracks
    FROM Datasets d
    LEFT JOIN Users u ON d.uploaded_by = u.user_id
    {where_clause}
    ORDER BY d.dataset_id
    """
    df = pd.read_sql(sql, conn)
    conn.close()
    return df


def validate_uav_csv_schema(csv_path: Path = DEFAULT_UAV_CSV, check_lines: int = 20) -> dict:
    """
    FR-06 & FR-39: Kiểm tra schema cột bắt buộc và kiểu dữ liệu trên file CSV UAV.
    Trả về thông báo lỗi chi tiết chỉ rõ dòng/cột bị sai nếu phát hiện lỗi.
    """
    if not csv_path.exists():
        return {"is_valid": False, "errors": [f"Không tìm thấy file: {csv_path}"]}

    errors = []
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        header_raw = f.readline().strip()
        header_cols = [c.strip().lower() for c in header_raw.rstrip("; ").split(";")]

        missing_cols = [c for c in REQUIRED_PNEUMA_COLS if c not in header_cols]
        if missing_cols:
            errors.append(f"Dòng 1 (Header): Thiếu các cột bắt buộc: {missing_cols}")
            return {"is_valid": False, "header": header_cols, "errors": errors}

        for line_no in range(2, 2 + check_lines):
            line = f.readline()
            if not line:
                break
            parts = line.rstrip("\r\n; ").split(";")
            if len(parts) < 10:
                errors.append(f"Dòng {line_no}: Chỉ có {len(parts)} cột (yêu cầu tối thiểu 10 cột).")
                continue
            for col_idx, col_name in [(0, "track_id"), (2, "traveled_d"), (3, "avg_speed"),
                                      (4, "lat"), (5, "lon"), (6, "speed"), (9, "time")]:
                try:
                    float(parts[col_idx].strip())
                except ValueError:
                    errors.append(
                        f"Dòng {line_no}, Cột {col_idx + 1} ({col_name}): "
                        f"Giá trị '{parts[col_idx]}' không phải kiểu số hợp lệ."
                    )

    return {
        "is_valid": len(errors) == 0,
        "file_name": csv_path.name,
        "file_size_mb": round(csv_path.stat().st_size / (1024 ** 2), 2),
        "header": header_cols,
        "checked_sample_lines": check_lines,
        "errors": errors,
    }


def preview_uav_csv(csv_path: Path = DEFAULT_UAV_CSV, n_rows: int = 5) -> pd.DataFrame:
    """FR-05: Xem trước N phương tiện đầu tiên và thống kê số khung hình của từng xe."""
    rows = []
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        _ = f.readline()
        for _ in range(n_rows):
            line = f.readline()
            if not line:
                break
            parts = [p.strip() for p in line.rstrip("\r\n; ").split(";")]
            if len(parts) < 10:
                continue
            n_frames_25hz = (len(parts) - 4) // 6
            rows.append({
                "source_track_id": int(float(parts[0])),
                "vehicle_type": parts[1],
                "traveled_d_m": float(parts[2]),
                "avg_speed_kmh": float(parts[3]),
                "first_lat": float(parts[4]),
                "first_lon": float(parts[5]),
                "total_points_25Hz": n_frames_25hz,
                "duration_sec": round(n_frames_25hz / 25.0, 1),
            })
    return pd.DataFrame(rows)


def register_dataset_version(
    name: str,
    source_type: str,
    location_name: str,
    file_path: str,
    uploaded_by: int = 2,
    frame_rate_hz: float = 25.0,
    recording_start_time: str = "2018-10-29 08:30:00",
    db_path: Path = DB_PATH,
) -> dict:
    """
    FR-04, FR-07, FR-10: Đăng ký tập dữ liệu mới vào bảng Datasets.
    Tự động tăng version_tag (v1.0 -> v1.1 -> v1.2...) để không bao giờ ghi đè phiên bản cũ.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()
    existing = cur.execute(
        "SELECT version_tag FROM Datasets WHERE name = ? ORDER BY dataset_id DESC LIMIT 1",
        (name,),
    ).fetchone()

    if not existing:
        next_version = "v1.0"
    else:
        prev_tag = str(existing[0]).lstrip("vV")
        try:
            major, minor = prev_tag.split(".")
            next_version = f"v{int(major)}.{int(minor) + 1}"
        except ValueError:
            next_version = f"v1.{cur.execute('SELECT COUNT(*) FROM Datasets WHERE name = ?', (name,)).fetchone()[0]}"

    cur.execute(
        """INSERT INTO Datasets
           (name, source_type, version_tag, location_name, recording_start_time, frame_rate_hz, file_path, status, uploaded_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'Uploaded', ?)""",
        (name, source_type, next_version, location_name, recording_start_time, frame_rate_hz, file_path, uploaded_by),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "dataset_id": new_id, "name": name, "version_tag": next_version}


def archive_dataset(dataset_id: int, db_path: Path = DB_PATH) -> dict:
    """FR-09: Lưu trữ (Archive) dataset - ẩn khỏi danh sách chính nhưng bảo toàn dữ liệu."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE Datasets SET status = 'Archived' WHERE dataset_id = ?", (dataset_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    if affected == 0:
        return {"status": "ERROR", "message": f"Không tìm thấy dataset_id={dataset_id}."}
    return {"status": "SUCCESS", "dataset_id": dataset_id, "new_status": "Archived"}


def delete_dataset(dataset_id: int, db_path: Path = DB_PATH) -> dict:
    """
    FR-08 (Quy tắc BR-13): Chỉ cho phép xóa dataset khi KHÔNG có thí nghiệm (Experiments) nào tham chiếu.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()
    exp_cnt = cur.execute("SELECT COUNT(*) FROM Experiments WHERE dataset_id = ?", (dataset_id,)).fetchone()[0]
    if exp_cnt > 0:
        conn.close()
        return {
            "status": "BLOCKED",
            "dataset_id": dataset_id,
            "referenced_experiments": exp_cnt,
            "message": f"Không được xóa dataset_id={dataset_id} vì đang có {exp_cnt} thực nghiệm tham chiếu (BR-13). Hãy dùng Archive!",
        }

    cur.execute("DELETE FROM Datasets WHERE dataset_id = ?", (dataset_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    if affected == 0:
        return {"status": "ERROR", "message": f"Không tìm thấy dataset_id={dataset_id}."}
    return {"status": "SUCCESS", "dataset_id": dataset_id, "message": "Đã xóa dataset thành công."}


def parse_pneuma_uav_csv(
    csv_path: Path = DEFAULT_UAV_CSV, step_frames: int = 25, max_vehicles: int | None = None
) -> pd.DataFrame:
    """
    Đọc file quỹ đạo UAV pNEUMA (dạng rộng 25 Hz) và lấy mẫu về dạng chuẩn Long Format (1 Hz).
    Nếu truyền `max_vehicles` (ví dụ 300), hàm chỉ đọc 300 xe đầu để kiểm thử nhanh trong < 0.5 giây.
    """
    raw_points = []
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        _ = f.readline()
        veh_read = 0
        for line in f:
            if max_vehicles is not None and veh_read >= max_vehicles:
                break
            parts = line.rstrip("\r\n; ").split(";")
            if len(parts) < 10:
                continue
            try:
                tid = int(float(parts[0].strip()))
                vtype = parts[1].strip()
                traveled_d = float(parts[2].strip())
                avg_spd = float(parts[3].strip())
            except ValueError:
                continue

            veh_read += 1
            n_pts = (len(parts) - 4) // 6
            for idx in range(0, n_pts, step_frames):
                b = 4 + idx * 6
                try:
                    raw_points.append((
                        tid, vtype, traveled_d, avg_spd,
                        float(parts[b]), float(parts[b + 1]), float(parts[b + 2]),
                        float(parts[b + 3]), float(parts[b + 4]), float(parts[b + 5]),
                    ))
                except ValueError:
                    raw_points.append((tid, vtype, traveled_d, avg_spd,
                                       np.nan, np.nan, np.nan, np.nan, np.nan, np.nan))

    return pd.DataFrame(
        raw_points,
        columns=[
            "source_track_id", "vehicle_type", "traveled_d_m", "avg_speed_kmh",
            "lat", "lon", "speed_kmh", "lon_acc_ms2", "lat_acc_ms2", "time_sec",
        ],
    )


def clean_and_validate_trajectories(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    FR-11 & FR-12: Thực hiện làm sạch 4 bước dữ liệu quỹ đạo UAV, chuyển đổi tọa độ sang mét (x_pos, y_pos)
    và sinh Bảng báo cáo chất lượng dữ liệu (số lỗi từng bước & % bản ghi bị loại).
    """
    n0_pts, n0_veh = len(df_raw), int(df_raw["source_track_id"].nunique())

    # Bước 1: Loại bỏ giá trị thiếu (NaN) và bản ghi trùng thời điểm của cùng 1 xe
    df_s1 = df_raw.dropna(subset=["source_track_id", "lat", "lon", "speed_kmh", "time_sec"]).copy()
    df_s1 = df_s1.drop_duplicates(subset=["source_track_id", "time_sec"], keep="first")
    n1_pts, n1_veh = len(df_s1), int(df_s1["source_track_id"].nunique())

    # Bước 2: Loại bỏ xe đỗ tĩnh ven đường (tổng quãng đường di chuyển < 5.0 mét)
    df_s2 = df_s1[df_s1["traveled_d_m"] >= 5.0].copy()
    n2_pts, n2_veh = len(df_s2), int(df_s2["source_track_id"].nunique())

    # Bước 3: Lọc bỏ ngoại lai vận tốc ngoài [0, 80] km/h và gia tốc |acc| > 8 m/s²
    cond_spd = (df_s2["speed_kmh"] >= 0.0) & (df_s2["speed_kmh"] <= 80.0)
    cond_acc = (df_s2["lon_acc_ms2"].abs() <= 8.0) & (df_s2["lat_acc_ms2"].abs() <= 8.0)
    df_s3 = df_s2[cond_spd & cond_acc].copy()
    n3_pts, n3_veh = len(df_s3), int(df_s3["source_track_id"].nunique())

    # Bước 4: Lọc bỏ các quỹ đạo quá ngắn (< 5 giây quan sát) & sắp xếp chuẩn theo thời gian
    track_len = df_s3.groupby("source_track_id")["time_sec"].transform("count")
    df_clean = df_s3[track_len >= 5].sort_values(["source_track_id", "time_sec"]).reset_index(drop=True)
    n4_pts, n4_veh = len(df_clean), int(df_clean["source_track_id"].nunique())

    # Bước 5: Quy đổi tọa độ địa lý (lat, lon) sang tọa độ phẳng Đề-các (x_pos, y_pos) tính bằng mét
    if not df_clean.empty:
        lat_min = float(df_clean["lat"].min())
        lon_min = float(df_clean["lon"].min())
        lat0_rad = float(np.radians(df_clean["lat"].mean()))

        df_clean["x_pos"] = ((df_clean["lon"] - lon_min) * 111320.0 * np.cos(lat0_rad)).round(3)
        df_clean["y_pos"] = ((df_clean["lat"] - lat_min) * 110540.0).round(3)
        df_clean["speed_ms"] = (df_clean["speed_kmh"] / 3.6).round(2)
        df_clean["acc_ms2"] = df_clean["lon_acc_ms2"].round(2)
        df_clean["frame_id"] = (df_clean["time_sec"] * 25).round().astype(int)
        df_clean["timestamp_ms"] = (df_clean["time_sec"] * 1000).round().astype(int)

        dx = df_clean.groupby("source_track_id")["x_pos"].diff().fillna(0.0)
        dy = df_clean.groupby("source_track_id")["y_pos"].diff().fillna(0.0)
        df_clean["heading_deg"] = np.degrees(np.arctan2(dy, dx)).round(2)

    base = max(n0_pts, 1)
    quality_report = pd.DataFrame([
        {
            "Bước kiểm tra & làm sạch": "0. Dữ liệu thô ban đầu (1 Hz)",
            "Số điểm còn lại": n0_pts,
            "Số điểm bị loại": 0,
            "Tỷ lệ loại (%)": 0.0,
            "Số xe còn lại": n0_veh,
        },
        {
            "Bước kiểm tra & làm sạch": "1. Bỏ giá trị thiếu (NaN) & bản ghi trùng",
            "Số điểm còn lại": n1_pts,
            "Số điểm bị loại": n0_pts - n1_pts,
            "Tỷ lệ loại (%)": round((n0_pts - n1_pts) * 100.0 / base, 2),
            "Số xe còn lại": n1_veh,
        },
        {
            "Bước kiểm tra & làm sạch": "2. Loại xe đỗ tĩnh ven đường (< 5m)",
            "Số điểm còn lại": n2_pts,
            "Số điểm bị loại": n1_pts - n2_pts,
            "Tỷ lệ loại (%)": round((n1_pts - n2_pts) * 100.0 / base, 2),
            "Số xe còn lại": n2_veh,
        },
        {
            "Bước kiểm tra & làm sạch": "3. Lọc nhiễu vận tốc (>80km/h) & gia tốc (>8m/s²)",
            "Số điểm còn lại": n3_pts,
            "Số điểm bị loại": n2_pts - n3_pts,
            "Tỷ lệ loại (%)": round((n2_pts - n3_pts) * 100.0 / base, 2),
            "Số xe còn lại": n3_veh,
        },
        {
            "Bước kiểm tra & làm sạch": "4. Loại quỹ đạo đứt quãng ngắn (< 5 giây)",
            "Số điểm còn lại": n4_pts,
            "Số điểm bị loại": n3_pts - n4_pts,
            "Tỷ lệ loại (%)": round((n3_pts - n4_pts) * 100.0 / base, 2),
            "Số xe còn lại": n4_veh,
        },
    ])
    return df_clean, quality_report


def get_db_trajectory_summary(dataset_id: int = 1, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Tổng hợp nhanh trạng thái dữ liệu quỹ đạo đã nạp trong CSDL của một Dataset."""
    conn = get_connection(db_path)
    sql = """
    SELECT
        d.dataset_id,
        d.name,
        d.version_tag,
        d.status,
        (SELECT COUNT(*) FROM Tracks t WHERE t.dataset_id = d.dataset_id) AS so_phuong_tien_tracks,
        (SELECT COUNT(*) FROM TrajectoryPoints tp
         JOIN Tracks t ON tp.track_id = t.track_id WHERE t.dataset_id = d.dataset_id) AS so_diem_quy_dao_db,
        (SELECT COUNT(*) FROM TrafficSpatialZones z WHERE z.dataset_id = d.dataset_id) AS so_vung_khong_gian,
        (SELECT COUNT(*) FROM TrafficAggregatedMetrics m WHERE m.dataset_id = d.dataset_id) AS so_ban_ghi_chuoi_thoi_gian
    FROM Datasets d
    WHERE d.dataset_id = ?
    """
    df = pd.read_sql(sql, conn, params=(dataset_id,))
    conn.close()
    return df


def run_demo() -> None:
    """Chạy kiểm thử độc lập toàn bộ chức năng của Module 1."""
    print("=" * 85)
    print("📂 MODULE 1 (M1): QUẢN LÝ DATASET & KIỂM TRA CHẤT LƯỢNG DỮ LIỆU QUỸ ĐẠO UAV")
    print("=" * 85)

    print("\n1️⃣ Danh sách Dataset hiện có trong CSDL (FR-07, FR-10):")
    print(list_datasets(include_archived=True, db_path=DB_PATH).to_string(index=False))

    print("\n2️⃣ Thống kê dữ liệu quỹ đạo đã nạp vào 4 bảng CSDL của dataset_id=1:")
    print(get_db_trajectory_summary(dataset_id=1, db_path=DB_PATH).to_string(index=False))

    if DEFAULT_UAV_CSV.exists():
        print(f"\n3️⃣ Kiểm tra Schema file CSV gốc '{DEFAULT_UAV_CSV.name}' (FR-06, FR-39):")
        schema_res = validate_uav_csv_schema(DEFAULT_UAV_CSV, check_lines=25)
        print(f"   • Hợp lệ: {schema_res['is_valid']} | Dung lượng: {schema_res['file_size_mb']} MB | Lỗi: {schema_res['errors']}")

        print("\n4️⃣ Xem trước 5 phương tiện đầu tiên trong file CSV (FR-05):")
        print(preview_uav_csv(DEFAULT_UAV_CSV, n_rows=5).to_string(index=False))

        print("\n5️⃣ Minh họa quy trình làm sạch 4 bước & Báo cáo chất lượng trên mẫu 500 xe đầu (FR-11, FR-12):")
        df_sample_raw = parse_pneuma_uav_csv(DEFAULT_UAV_CSV, step_frames=25, max_vehicles=500)
        _, quality_df = clean_and_validate_trajectories(df_sample_raw)
        print(quality_df.to_string(index=False))
    else:
        print(
            "\nℹ️ Ghi chú (3️⃣-5️⃣): File CSV thô gốc 1.72 GB (20181029_dX_0830_0900.csv) được lược bỏ trên GitHub (>100MB)."
            "\n   Dữ liệu sạch (8,255 xe & 30,000 điểm) đã có sẵn trong UrbanTrafficAnalyticsDB.db. Xem trước 5 xe đầu:"
        )
        conn_prev = get_connection(DB_PATH)
        print(pd.read_sql("SELECT * FROM Tracks LIMIT 5", conn_prev).to_string(index=False))
        conn_prev.close()

    print("\n6️⃣ Kiểm thử quy tắc quản lý phiên bản, Archive và chặn xóa Dataset đang có thực nghiệm (FR-07, FR-08, FR-09):")
    print("   • Thử xóa dataset_id=1 (đang có 9 thí nghiệm):", delete_dataset(1, DB_PATH))

    new_ver = register_dataset_version(
        name="UAV_pNEUMA_20181029_0830_0900",
        source_type="pNEUMA_UAV",
        location_name="Athens Urban Center (Bản thử nghiệm quản lý phiên bản)",
        file_path="Tuan_02_04_Xu_ly_du_lieu_UAV/20181029_dX_0830_0900.csv",
        uploaded_by=2,
        db_path=DB_PATH,
    )
    print("   • Đăng ký phiên bản mới tự động nâng version_tag:", new_ver)
    new_ds_id = new_ver["dataset_id"]
    print("   • Chuyển phiên bản mới sang trạng thái Archived:", archive_dataset(new_ds_id, DB_PATH))
    print("   • Xóa phiên bản thử nghiệm (chưa có thí nghiệm nên cho phép xóa):", delete_dataset(new_ds_id, DB_PATH))

    # Reset bộ đếm AUTOINCREMENT của bảng Datasets để giữ CSDL gọn sạch
    conn = get_connection(DB_PATH)
    conn.execute("UPDATE sqlite_sequence SET seq = (SELECT MAX(dataset_id) FROM Datasets) WHERE name = 'Datasets'")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    run_demo()
