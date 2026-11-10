r"""
QUẢN LÝ CƠ SỞ DỮ LIỆU ĐỘNG 9 BẢNG (db_manager.py)
===================================================
Thiết kế mới hoàn toàn cho dự án `8_LamLaiDuAn` (KHÔNG PHÂN QUYỀN, ĐẦY ĐỦ 6 MODULE):
  1. DatasetImports        : Quản lý thông tin file dữ liệu (.xlsx / .xls / .csv <= 3 GB) được kéo thả vào.
  2. DynamicZones          : Danh mục Khu vực đô thị được chia TỰ ĐỘNG từ dữ liệu nạp vào.
  3. DynamicTimeFrames     : Danh mục Khung giờ được chia TỰ ĐỘNG từ khoảng thời gian trong file.
  4. CleanedTrajectories   : Dữ liệu quỹ đạo phương tiện UAV sau khi đã tiền xử lý & làm sạch.
  5. TrafficPatternMetrics : Chỉ số giao thông tổng hợp theo từng Khu vực động & Khung giờ động.
  6. ForecastComparisons   : Kết quả đánh giá & nhận xét so sánh giữa ARIMA và Prophet.
  7. ForecastPoints        : Chuỗi điểm dự báo ARIMA & Prophet (Ngày gốc Day 0, Dự báo Ngày +1, Ngày +2 & Khung giờ).
  8. ExperimentRuns        : Quản lý thực nghiệm, siêu tham số & hỗ trợ tái lập nghiên cứu (Module 5).
  9. GeneratedReports      : Quản lý báo cáo phân tích/dự báo/hiệu năng & lịch sử xuất PDF/Excel (Module 6).
"""

import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

_VENV_SITE = BASE_DIR.parent / "4_Code" / ".venv" / "Lib" / "site-packages"
if _VENV_SITE.exists() and sys.version_info[:2] == (3, 14) and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

try:
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

DB_DIR = BASE_DIR / "database"
DB_PATH = DB_DIR / "UrbanTrafficDynamicDB.db"

ALL_9_TABLES = [
    ("DatasetImports",        "Module 1: Quản lý file .xlsx / .xls / .csv (<= 3 GB) nạp vào"),
    ("DynamicZones",          "Module 1 & 2: Danh mục Khu vực chia tự động từ dữ liệu"),
    ("DynamicTimeFrames",     "Module 1, 2 & 3: Danh mục Khung giờ chia tự động từ dữ liệu"),
    ("CleanedTrajectories",   "Module 1, 2 & 4: Quỹ đạo phương tiện UAV sau tiền xử lý"),
    ("TrafficPatternMetrics", "Module 2, 3, 4 & 6: Chỉ số giao thông theo Khu vực & Khung giờ"),
    ("ForecastComparisons",   "Module 3, 4 & 6: Đánh giá & Nhận xét so sánh ARIMA vs Prophet"),
    ("ForecastPoints",        "Module 3, 4 & 6: Điểm dự báo ARIMA & Prophet (Ngày 0, Ngày +1, Ngày +2)"),
    ("ExperimentRuns",        "Module 5: Cấu hình thực nghiệm, siêu tham số & tái lập nghiên cứu"),
    ("GeneratedReports",      "Module 6: Quản lý báo cáo phân tích/dự báo & xuất file PDF / Excel"),
    ("AnalysisRuns",          "Lưu kết quả tổng hợp chuỗi thời gian đa Dataset"),
    ("AnalysisRunDatasets",   "Liên kết Analysis Run với các Dataset đã chọn"),
    ("ForecastRuns",          "Lưu lịch sử dự báo ARIMA/Prophet đa Dataset"),
    ("ForecastRunDatasets",   "Liên kết Forecast Run với các Dataset đã chọn"),
    ("ForecastResults",       "Lưu điểm kiểm tra và dự báo tương lai"),
]
ALL_7_TABLES = ALL_9_TABLES

DDL_9_TABLES_SQLITE = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS DatasetImports (
    import_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name               TEXT    NOT NULL,
    file_extension          TEXT    NOT NULL CHECK (file_extension IN ('.xlsx', '.xls', '.csv')),
    file_size_kb            REAL    NOT NULL CHECK (file_size_kb >= 0),
    raw_row_count           INTEGER NOT NULL CHECK (raw_row_count >= 0),
    cleaned_row_count       INTEGER NOT NULL CHECK (cleaned_row_count >= 0),
    removed_missing_dup     INTEGER NOT NULL DEFAULT 0,
    removed_stationary      INTEGER NOT NULL DEFAULT 0,
    removed_outliers        INTEGER NOT NULL DEFAULT 0,
    dynamic_zone_count      INTEGER NOT NULL DEFAULT 0,
    dynamic_timeframe_count INTEGER NOT NULL DEFAULT 0,
    time_range_start        TEXT    NULL,
    time_range_end          TEXT    NULL,
    status_message          TEXT    NOT NULL,
    imported_at             TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS DynamicZones (
    zone_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id               INTEGER NOT NULL,
    zone_code               TEXT    NOT NULL,
    zone_name               TEXT    NOT NULL,
    partition_method        TEXT    NOT NULL DEFAULT 'Data_Driven',
    x_min_m                 REAL    NOT NULL,
    x_max_m                 REAL    NOT NULL,
    y_min_m                 REAL    NOT NULL,
    y_max_m                 REAL    NOT NULL,
    road_length_km          REAL    NOT NULL CHECK (road_length_km > 0),
    FOREIGN KEY (import_id) REFERENCES DatasetImports(import_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS DynamicTimeFrames (
    timeframe_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id               INTEGER NOT NULL,
    timeframe_code          TEXT    NOT NULL,
    timeframe_label         TEXT    NOT NULL,
    start_time_str          TEXT    NOT NULL,
    end_time_str            TEXT    NOT NULL,
    start_epoch_sec         REAL    NOT NULL,
    end_epoch_sec           REAL    NOT NULL,
    duration_minutes        REAL    NOT NULL CHECK (duration_minutes > 0),
    is_peak_timeframe       INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (import_id) REFERENCES DatasetImports(import_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS CleanedTrajectories (
    trajectory_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id               INTEGER NOT NULL,
    zone_id                 INTEGER NOT NULL,
    timeframe_id            INTEGER NOT NULL,
    vehicle_id              TEXT    NOT NULL,
    vehicle_type            TEXT    NOT NULL,
    recorded_time_str       TEXT    NOT NULL,
    time_sec                REAL    NOT NULL,
    x_coord_m               REAL    NOT NULL,
    y_coord_m               REAL    NOT NULL,
    speed_kmh               REAL    NOT NULL CHECK (speed_kmh >= 0 AND speed_kmh <= 150),
    accel_ms2               REAL    NOT NULL CHECK (accel_ms2 >= -15 AND accel_ms2 <= 15),
    lane_no                 INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (import_id) REFERENCES DatasetImports(import_id) ON DELETE CASCADE,
    FOREIGN KEY (zone_id) REFERENCES DynamicZones(zone_id) ON DELETE CASCADE,
    FOREIGN KEY (timeframe_id) REFERENCES DynamicTimeFrames(timeframe_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS TrafficPatternMetrics (
    metric_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id               INTEGER NOT NULL,
    zone_id                 INTEGER NOT NULL,
    timeframe_id            INTEGER NOT NULL,
    window_index            INTEGER NOT NULL,
    window_time_label       TEXT    NOT NULL,
    window_duration_sec     INTEGER NOT NULL CHECK (window_duration_sec > 0),
    vehicle_count           INTEGER NOT NULL CHECK (vehicle_count >= 0),
    car_count               INTEGER NOT NULL DEFAULT 0,
    motorbike_count         INTEGER NOT NULL DEFAULT 0,
    bus_truck_count         INTEGER NOT NULL DEFAULT 0,
    avg_speed_kmh           REAL    NOT NULL CHECK (avg_speed_kmh >= 0),
    traffic_density_veh_km  REAL    NOT NULL CHECK (traffic_density_veh_km >= 0),
    traffic_flow_veh_h      REAL    NOT NULL CHECK (traffic_flow_veh_h >= 0),
    slow_vehicle_ratio_pct  REAL    NOT NULL DEFAULT 0,
    is_peak_hour            INTEGER NOT NULL DEFAULT 0,
    is_hotspot              INTEGER NOT NULL DEFAULT 0,
    hotspot_location        TEXT    NULL,
    hotspot_score           REAL    NOT NULL DEFAULT 0,
    congestion_level        TEXT    NOT NULL CHECK (congestion_level IN ('Free Flow', 'Moderate', 'Heavy', 'Gridlock')),
    FOREIGN KEY (import_id) REFERENCES DatasetImports(import_id) ON DELETE CASCADE,
    FOREIGN KEY (zone_id) REFERENCES DynamicZones(zone_id) ON DELETE CASCADE,
    FOREIGN KEY (timeframe_id) REFERENCES DynamicTimeFrames(timeframe_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ForecastComparisons (
    comparison_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id               INTEGER NOT NULL,
    zone_id                 INTEGER NOT NULL,
    arima_order_str         TEXT    NOT NULL,
    arima_mae               REAL    NOT NULL,
    arima_rmse              REAL    NOT NULL,
    arima_mape_pct          REAL    NOT NULL,
    arima_r2                REAL    NOT NULL,
    prophet_seasonality_str TEXT    NOT NULL,
    prophet_mae             REAL    NOT NULL,
    prophet_rmse            REAL    NOT NULL,
    prophet_mape_pct        REAL    NOT NULL,
    prophet_r2              REAL    NOT NULL,
    better_model            TEXT    NOT NULL CHECK (better_model IN ('ARIMA', 'Prophet')),
    rmse_improvement_pct    REAL    NOT NULL,
    commentary_text         TEXT    NOT NULL,
    created_at              TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (import_id) REFERENCES DatasetImports(import_id) ON DELETE CASCADE,
    FOREIGN KEY (zone_id) REFERENCES DynamicZones(zone_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ForecastPoints (
    point_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    comparison_id           INTEGER NOT NULL,
    timeframe_id            INTEGER NULL,
    day_offset              INTEGER NOT NULL DEFAULT 0 CHECK (day_offset IN (0, 1, 2)),
    forecast_date_label     TEXT    NOT NULL DEFAULT 'Ngày gốc (Day 0)',
    step_index              INTEGER NOT NULL,
    time_label              TEXT    NOT NULL,
    phase_type              TEXT    NOT NULL CHECK (phase_type IN ('Train', 'Test', 'Future_Day1', 'Future_Day2')),
    actual_density          REAL    NULL,
    arima_predicted         REAL    NOT NULL,
    arima_lower_95          REAL    NOT NULL,
    arima_upper_95          REAL    NOT NULL,
    prophet_predicted       REAL    NOT NULL,
    prophet_lower_95        REAL    NOT NULL,
    prophet_upper_95        REAL    NOT NULL,
    FOREIGN KEY (comparison_id) REFERENCES ForecastComparisons(comparison_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ExperimentRuns (
    experiment_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id                 INTEGER NOT NULL,
    zone_id                   INTEGER NOT NULL,
    experiment_code           TEXT    NOT NULL,
    experiment_name           TEXT    NOT NULL,
    temporal_interval_sec     INTEGER NOT NULL CHECK (temporal_interval_sec > 0),
    train_ratio               REAL    NOT NULL DEFAULT 0.75,
    arima_order_str           TEXT    NOT NULL,
    prophet_fourier_k         INTEGER NOT NULL DEFAULT 3,
    prophet_changepoint_scale REAL    NOT NULL DEFAULT 0.15,
    random_seed               INTEGER NOT NULL DEFAULT 42,
    dataset_version           TEXT    NOT NULL DEFAULT 'v1.0',
    software_version          TEXT    NOT NULL DEFAULT 'UTA-Platform v2.0',
    arima_mae                 REAL    NOT NULL,
    arima_rmse                REAL    NOT NULL,
    arima_mape_pct            REAL    NOT NULL,
    arima_r2                  REAL    NOT NULL,
    prophet_mae               REAL    NOT NULL,
    prophet_rmse              REAL    NOT NULL,
    prophet_mape_pct          REAL    NOT NULL,
    prophet_r2                REAL    NOT NULL,
    winner_model              TEXT    NOT NULL CHECK (winner_model IN ('ARIMA', 'Prophet')),
    execution_time_ms         REAL    NOT NULL DEFAULT 45.0,
    reproducibility_hash      TEXT    NOT NULL,
    notes                     TEXT    NULL,
    created_at                TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (import_id) REFERENCES DatasetImports(import_id) ON DELETE CASCADE,
    FOREIGN KEY (zone_id) REFERENCES DynamicZones(zone_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS GeneratedReports (
    report_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id                 INTEGER NOT NULL,
    report_code               TEXT    NOT NULL,
    report_title              TEXT    NOT NULL,
    report_type               TEXT    NOT NULL CHECK (report_type IN ('Traffic_Analysis', 'Forecast_2Days', 'Performance_Experiment', 'Comprehensive_Full')),
    export_format             TEXT    NOT NULL CHECK (export_format IN ('PDF', 'EXCEL', 'WEB_PREVIEW')),
    zone_scope                TEXT    NOT NULL,
    horizon_scope             TEXT    NOT NULL,
    summary_highlights        TEXT    NOT NULL,
    generated_at              TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (import_id) REFERENCES DatasetImports(import_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS IX_Traj_Zone_Time ON CleanedTrajectories(zone_id, timeframe_id);
CREATE INDEX IF NOT EXISTS IX_Metrics_Zone_Time ON TrafficPatternMetrics(zone_id, timeframe_id);
CREATE TABLE IF NOT EXISTS AnalysisRuns (
    analysis_run_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    aggregation_interval_minutes INTEGER NOT NULL,
    target_metric           TEXT NOT NULL,
    status                  TEXT NOT NULL,
    summary_json            TEXT NOT NULL,
    created_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS AnalysisRunDatasets (
    analysis_run_id         INTEGER NOT NULL,
    import_id               INTEGER NOT NULL,
    PRIMARY KEY (analysis_run_id, import_id),
    FOREIGN KEY (analysis_run_id) REFERENCES AnalysisRuns(analysis_run_id),
    FOREIGN KEY (import_id) REFERENCES DatasetImports(import_id)
);

CREATE TABLE IF NOT EXISTS ForecastRuns (
    forecast_run_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_run_id         INTEGER NOT NULL,
    training_start          TEXT NOT NULL,
    training_end            TEXT NOT NULL,
    forecast_horizon        INTEGER NOT NULL,
    aggregation_interval_minutes INTEGER NOT NULL,
    target_metric           TEXT NOT NULL,
    model_parameters_json   TEXT NOT NULL,
    evaluation_metrics_json TEXT NOT NULL,
    status                  TEXT NOT NULL,
    created_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (analysis_run_id) REFERENCES AnalysisRuns(analysis_run_id)
);

CREATE TABLE IF NOT EXISTS ForecastRunDatasets (
    forecast_run_id         INTEGER NOT NULL,
    import_id               INTEGER NOT NULL,
    PRIMARY KEY (forecast_run_id, import_id),
    FOREIGN KEY (forecast_run_id) REFERENCES ForecastRuns(forecast_run_id),
    FOREIGN KEY (import_id) REFERENCES DatasetImports(import_id)
);

CREATE TABLE IF NOT EXISTS ForecastResults (
    forecast_result_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_run_id         INTEGER NOT NULL,
    model_name              TEXT NOT NULL,
    result_type             TEXT NOT NULL CHECK (result_type IN ('holdout', 'future')),
    timestamp               TEXT NOT NULL,
    actual_value            REAL NULL,
    predicted_value         REAL NOT NULL,
    lower_bound             REAL NULL,
    upper_bound             REAL NULL,
    FOREIGN KEY (forecast_run_id) REFERENCES ForecastRuns(forecast_run_id) ON DELETE CASCADE
);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Mở kết nối tới CSDL UrbanTrafficDynamicDB.db và bật kiểm tra khóa ngoại."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Khởi tạo schema bổ sung mà không xóa dữ liệu hiện có."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    conn.executescript(DDL_9_TABLES_SQLITE)
    dataset_columns = {
        row[1] for row in cur.execute("PRAGMA table_info(DatasetImports)").fetchall()
    }
    additions = {
        "dataset_uuid": "TEXT",
        "storage_path": "TEXT",
        "checksum_sha256": "TEXT",
        "capture_date": "TEXT",
        "drone_id": "TEXT",
        "start_time": "TEXT",
        "end_time": "TEXT",
        "duration_minutes": "REAL",
        "processing_status": "TEXT NOT NULL DEFAULT 'saved'",
        "validation_status": "TEXT NOT NULL DEFAULT 'legacy'",
        "is_deleted": "INTEGER NOT NULL DEFAULT 0",
    }
    for column, definition in additions.items():
        if column not in dataset_columns:
            cur.execute(f"ALTER TABLE DatasetImports ADD COLUMN {column} {definition}")

    missing_legacy_forecast_columns = {
        row[1] for row in cur.execute("PRAGMA table_info(ForecastPoints)").fetchall()
    }
    if "day_offset" not in missing_legacy_forecast_columns:
        cur.execute(
            "ALTER TABLE ForecastPoints ADD COLUMN day_offset INTEGER NOT NULL DEFAULT 0"
        )
    if "timeframe_id" not in missing_legacy_forecast_columns:
        cur.execute("ALTER TABLE ForecastPoints ADD COLUMN timeframe_id INTEGER NULL")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS IX_ForecastPts_Comp_Day_TF "
        "ON ForecastPoints(comparison_id, day_offset, timeframe_id)"
    )

    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS UX_DatasetImports_UUID "
        "ON DatasetImports(dataset_uuid)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS IX_DatasetImports_Checksum "
        "ON DatasetImports(checksum_sha256)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS IX_DatasetImports_Capture "
        "ON DatasetImports(capture_date, drone_id, processing_status)"
    )
    legacy_rows = cur.execute(
        "SELECT import_id FROM DatasetImports "
        "WHERE dataset_uuid IS NULL OR dataset_uuid = ''"
    ).fetchall()
    for row in legacy_rows:
        cur.execute(
            "UPDATE DatasetImports SET dataset_uuid = ? WHERE import_id = ?",
            (str(uuid.uuid4()), row[0]),
        )
    conn.commit()
    conn.close()

