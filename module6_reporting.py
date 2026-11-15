r"""
MODULE 6: REPORTING — HỆ THỐNG KẾT XUẤT BÁO CÁO PHÂN TÍCH, DỰ BÁO & HIỆU NĂNG (module6_reporting.py)
=====================================================================================================
Đáp ứng đầy đủ yêu cầu Module 6 trong `1_nhu_cau_khach_hang.md`:
  1. Traffic analysis reports : Báo cáo tổng hợp lưu lượng, vận tốc, mật độ, khung giờ cao điểm & điểm nóng ùn tắc.
  2. Forecast reports         : Báo cáo dự báo ngắn hạn & mở rộng 2 ngày tiếp theo (+24h / +48h) giữa ARIMA và Prophet.
  3. Performance reports      : Báo cáo đánh giá sai số (MAE, RMSE, MAPE, R²) và kết quả thực nghiệm đa cấu hình.
  4. PDF export               : Kết xuất báo cáo định dạng PDF chuẩn in ấn nghiên cứu.
  5. Excel export             : Kết xuất báo cáo định dạng bảng tính Excel (.xlsx) đa bảng.
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

from db_manager import DB_PATH, get_connection

REPORT_TYPE_TITLES = {
    "Traffic_Analysis": "Báo Cáo Phân Tích Mẫu Hình Giao Thông & Điểm Nóng Ùn Tắc (Traffic Analysis Report)",
    "Forecast_2Days": "Báo Cáo Dự Báo Ngắn Hạn & 2 Ngày Tiếp Theo ARIMA vs Prophet (Forecast Report)",
    "Performance_Experiment": "Báo Cáo Đánh Giá Hiệu Năng & Thực Nghiệm Tái Lập (Performance Report)",
    "Comprehensive_Full": "Báo Cáo Tổng Hợp Toàn Hệ Thống Phân Tích & Dự Báo Giao Thông UAV (Full Report)",
}


def seed_default_reports(import_id: int, db_path: Path = DB_PATH) -> int:
    """Khởi tạo 4 bản ghi báo cáo tiêu chuẩn trong bảng `GeneratedReports` khi nạp file dữ liệu mới."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM GeneratedReports WHERE import_id = ?", (import_id,))

    imp_row = cur.execute(
        "SELECT file_name, cleaned_row_count, dynamic_zone_count, dynamic_timeframe_count FROM DatasetImports WHERE import_id = ?",
        (import_id,),
    ).fetchone()
    if not imp_row:
        conn.close()
        return 0

    f_name, clean_cnt, z_cnt, tf_cnt = str(imp_row[0]), int(imp_row[1]), int(imp_row[2]), int(imp_row[3])
    defaults = [
        (
            "RPT-01-TRAF",
            REPORT_TYPE_TITLES["Traffic_Analysis"],
            "Traffic_Analysis",
            "PDF",
            f"Tất cả {z_cnt} Khu vực động",
            f"Tất cả {tf_cnt} Khung giờ động",
            f"Tổng hợp {clean_cnt:,} quỹ đạo sạch từ file '{f_name}', nhận diện khung giờ cao điểm & điểm nóng ùn tắc.",
        ),
        (
            "RPT-02-FC2D",
            REPORT_TYPE_TITLES["Forecast_2Days"],
            "Forecast_2Days",
            "EXCEL",
            f"Tất cả {z_cnt} Khu vực động",
            "Ngày gốc (Day 0) + Dự báo 2 Ngày sau đó (+24h / +48h)",
            "Đối chiếu chuỗi dự báo ARIMA và Prophet kèm khoảng tin cậy 95% cho Ngày hiện tại, Ngày +1 và Ngày +2.",
        ),
        (
            "RPT-03-PERF",
            REPORT_TYPE_TITLES["Performance_Experiment"],
            "Performance_Experiment",
            "PDF",
            f"Tất cả {z_cnt} Khu vực động",
            "Đa khoảng gộp thời gian (30s, 60s, 300s, 900s)",
            "Đánh giá sai số MAE, RMSE, MAPE, R² và mã băm Reproducibility Hash đảm bảo tái lập nghiên cứu 100%.",
        ),
        (
            "RPT-04-FULL",
            REPORT_TYPE_TITLES["Comprehensive_Full"],
            "Comprehensive_Full",
            "EXCEL",
            f"Toàn bộ {z_cnt} Khu vực & {tf_cnt} Khung giờ",
            "Toàn diện (Day 0 + 2 Ngày tiếp theo)",
            f"Báo cáo tổng hợp đầy đủ 6 Module từ bộ dữ liệu '{f_name}' phục vụ lưu trữ và xuất bản khoa học.",
        ),
    ]

    for r_code, r_title, r_type, fmt, z_scope, h_scope, summary in defaults:
        cur.execute(
            """
            INSERT INTO GeneratedReports (
                import_id, report_code, report_title, report_type,
                export_format, zone_scope, horizon_scope, summary_highlights
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (import_id, r_code, r_title, r_type, fmt, z_scope, h_scope, summary),
        )

    conn.commit()
    conn.close()
    return len(defaults)


def log_and_generate_report(
    report_type: str = "Comprehensive_Full",
    export_format: str = "PDF",
    zone_scope: str = "Tất cả Khu vực động",
    horizon_scope: str = "Ngày gốc + Dự báo 2 ngày sau đó (+48h)",
    db_path: Path = DB_PATH,
    dataset_ids: list[int] | None = None,
) -> dict:
    """Ghi nhận lịch sử xuất báo cáo (PDF hoặc EXCEL) vào bảng `GeneratedReports` và trả về dữ liệu mới nhất."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    if dataset_ids:
        selected_ids = list(dict.fromkeys(int(value) for value in dataset_ids))
        placeholders = ",".join("?" for _ in selected_ids)
        imports = cur.execute(
            f"""
            SELECT import_id, file_name FROM DatasetImports
            WHERE import_id IN ({placeholders}) AND is_deleted = 0
              AND processing_status = 'saved'
            ORDER BY import_id DESC
            """,
            selected_ids,
        ).fetchall()
    else:
        imports = cur.execute(
            """
            SELECT import_id, file_name FROM DatasetImports
            WHERE is_deleted = 0 AND processing_status = 'saved'
            ORDER BY import_id DESC LIMIT 1
            """
        ).fetchall()
    if not imports:
        conn.close()
        raise ValueError("Chưa có dữ liệu trong Database để tạo báo cáo!")
    if dataset_ids and len(imports) != len(selected_ids):
        conn.close()
        raise ValueError("Một hoặc nhiều Dataset không hợp lệ.")

    selected_ids = [int(row[0]) for row in imports]
    f_name = ", ".join(str(row[1]) for row in imports)
    r_type = report_type if report_type in REPORT_TYPE_TITLES else "Comprehensive_Full"
    fmt = export_format.upper() if export_format.upper() in ("PDF", "EXCEL", "WEB_PREVIEW") else "PDF"

    r_title = REPORT_TYPE_TITLES[r_type]
    summary = (
        f"Kết xuất thành công {r_title} định dạng {fmt} trên phạm vi '{zone_scope}' "
        f"({horizon_scope}) từ nguồn dữ liệu '{f_name}'."
    )

    for imp_id in selected_ids:
        cnt = int(cur.execute("SELECT COUNT(*) FROM GeneratedReports").fetchone()[0]) + 1
        r_code = f"RPT-{cnt:02d}-{fmt[:3]}"
        cur.execute(
            """
            INSERT INTO GeneratedReports (
                import_id, report_code, report_title, report_type,
                export_format, zone_scope, horizon_scope, summary_highlights
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (imp_id, r_code, r_title, r_type, fmt, zone_scope, horizon_scope, summary),
        )
    conn.commit()
    conn.close()
    return get_module6_reporting_data(db_path, selected_ids)


def get_module6_reporting_data(
    db_path: Path = DB_PATH,
    dataset_ids: list[int] | None = None,
) -> dict:
    """Trả về toàn bộ dữ liệu tổng hợp phục vụ giao diện Module 6 và chức năng xuất PDF / Excel trên Web."""
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
        if len(imp_df) != len(selected_ids):
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
        return {"has_data": False, "message": "Chưa có dữ liệu trong Database. Vui lòng nạp file ở Module 1 trước!"}

    imp = imp_df.iloc[0]
    selected_ids = imp_df["import_id"].astype(int).tolist()
    placeholders = ",".join("?" for _ in selected_ids)

    # 1. Bảng tổng hợp Phân tích Giao thông theo Khu vực (Traffic Analysis Report)
    traffic_report_df = pd.read_sql(
        f"""
        SELECT z.zone_code AS Ma_Khu_Vuc,
               z.zone_name AS Ten_Khu_Vuc,
               z.road_length_km AS Chieu_Dai_Km,
               SUM(m.vehicle_count) AS Tong_Luot_Xe,
               ROUND(AVG(m.avg_speed_kmh), 2) AS Van_Toc_TB_Kmh,
               ROUND(AVG(m.traffic_density_veh_km), 2) AS Mat_Do_TB_Xe_Km,
               ROUND(MAX(m.traffic_density_veh_km), 2) AS Mat_Do_Dinh_Xe_Km,
               ROUND(AVG(m.traffic_flow_veh_h), 1) AS Luu_Luong_TB_Xe_Gio,
               SUM(m.is_peak_hour) AS So_Cua_So_Cao_Diem,
               SUM(m.is_hotspot) AS So_Diem_Nong_Un_Tac
        FROM TrafficPatternMetrics m
        JOIN DynamicZones z ON m.zone_id = z.zone_id
        WHERE m.import_id IN ({placeholders})
        GROUP BY z.zone_code, z.zone_name, z.road_length_km
        ORDER BY z.zone_code ASC
        """,
        conn,
        params=selected_ids,
    )

    # 2. Bảng tổng hợp Dự báo Ngắn hạn & 2 Ngày tiếp theo (Forecast Report)
    forecast_report_df = pd.read_sql(
        f"""
        SELECT z.zone_name AS Khu_Vuc,
               fc.arima_order_str AS Cau_Hinh_ARIMA,
               fc.arima_mae AS ARIMA_MAE,
               fc.arima_rmse AS ARIMA_RMSE,
               fc.arima_mape_pct AS ARIMA_MAPE_Pct,
               fc.arima_r2 AS ARIMA_R2,
               fc.prophet_seasonality_str AS Cau_Hinh_Prophet,
               fc.prophet_mae AS Prophet_MAE,
               fc.prophet_rmse AS Prophet_RMSE,
               fc.prophet_mape_pct AS Prophet_MAPE_Pct,
               fc.prophet_r2 AS Prophet_R2,
               fc.better_model AS Mo_Hinh_Toi_Uu,
               fc.rmse_improvement_pct AS Cai_Thien_RMSE_Pct,
               fc.commentary_text AS Nhan_Xet_Danh_Gia
        FROM ForecastComparisons fc
        JOIN DynamicZones z ON fc.zone_id = z.zone_id
        WHERE fc.import_id IN ({placeholders})
        ORDER BY fc.zone_id ASC
        """,
        conn,
        params=selected_ids,
    )

    # 3. Bảng tổng hợp Dự báo theo Tầm nhìn Ngày (Day 0, Ngày +1, Ngày +2)
    multiday_summary_df = pd.read_sql(
        f"""
        SELECT z.zone_name AS Khu_Vuc,
               fp.day_offset AS Ngay_Du_Bao_Offset,
               fp.forecast_date_label AS Tam_Nhin_Du_Bao,
               COUNT(*) AS So_Buoc_Thoi_Gian,
               ROUND(AVG(fp.actual_density), 2) AS Mat_Do_Tham_Chieu_TB,
               ROUND(AVG(fp.arima_predicted), 2) AS ARIMA_Du_Bao_TB,
               ROUND(MAX(fp.arima_predicted), 2) AS ARIMA_Du_Bao_Dinh,
               ROUND(AVG(fp.prophet_predicted), 2) AS Prophet_Du_Bao_TB,
               ROUND(MAX(fp.prophet_predicted), 2) AS Prophet_Du_Bao_Dinh
        FROM ForecastPoints fp
        JOIN ForecastComparisons fc ON fp.comparison_id = fc.comparison_id
        JOIN DynamicZones z ON fc.zone_id = z.zone_id
        WHERE fc.import_id IN ({placeholders})
        GROUP BY z.zone_id, z.zone_name, fp.day_offset, fp.forecast_date_label
        ORDER BY z.zone_id ASC, fp.day_offset ASC
        """,
        conn,
        params=selected_ids,
    )

    # 4. Bảng tổng hợp Hiệu năng & Thực nghiệm (Performance Report)
    experiment_report_df = pd.read_sql(
        f"""
        SELECT e.experiment_code AS Ma_Thuc_Nghiem,
               z.zone_name AS Khu_Vuc,
               e.temporal_interval_sec AS Khoang_Gop_Giay,
               e.train_ratio AS Ty_Le_Train,
               e.arima_order_str AS Bac_ARIMA,
               e.prophet_fourier_k AS Bac_Fourier_Prophet,
               e.arima_rmse AS ARIMA_RMSE,
               e.prophet_rmse AS Prophet_RMSE,
               e.winner_model AS Mo_Hinh_Thang,
               e.reproducibility_hash AS Ma_Bam_Tai_Lap
        FROM ExperimentRuns e
        JOIN DynamicZones z ON e.zone_id = z.zone_id
        WHERE e.import_id IN ({placeholders})
        ORDER BY e.experiment_id ASC
        """,
        conn,
        params=selected_ids,
    )

    reports_df = pd.read_sql(
        f"SELECT * FROM GeneratedReports WHERE import_id IN ({placeholders}) ORDER BY report_id DESC",
        conn,
        params=selected_ids,
    )
    if reports_df.empty:
        conn.close()
        for imp_id in selected_ids:
            seed_default_reports(imp_id, db_path)
        conn = get_connection(db_path)
        reports_df = pd.read_sql(
            f"SELECT * FROM GeneratedReports WHERE import_id IN ({placeholders}) ORDER BY report_id DESC",
            conn,
            params=selected_ids,
        )

    timeframe_count = int(conn.execute(
        f"""
        SELECT COUNT(DISTINCT timeframe_code)
        FROM DynamicTimeFrames
        WHERE import_id IN ({placeholders})
        """,
        selected_ids,
    ).fetchone()[0])
    conn.close()

    return {
        "has_data": True,
        "dataset_info": {
            "file_name": ", ".join(imp_df["file_name"].astype(str)),
            "cleaned_rows": int(imp_df["cleaned_row_count"].sum()),
            "zone_count": int(traffic_report_df["Ma_Khu_Vuc"].nunique()),
            "timeframe_count": timeframe_count,
            "time_range": f"{imp_df['time_range_start'].min()} -> {imp_df['time_range_end'].max()}",
            "imported_at": ", ".join(imp_df["imported_at"].astype(str)),
        },
        "traffic_analysis_table": traffic_report_df.to_dict(orient="records"),
        "forecast_comparison_table": forecast_report_df.to_dict(orient="records"),
        "multiday_forecast_table": multiday_summary_df.to_dict(orient="records"),
        "performance_experiment_table": experiment_report_df.to_dict(orient="records"),
        "reports_history": reports_df.to_dict(orient="records"),
        "selected_dataset_ids": selected_ids,
    }
