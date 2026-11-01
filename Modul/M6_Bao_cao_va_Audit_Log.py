"""
MODULE 6 (M6): XUẤT BÁO CÁO (CSV / EXCEL / PDF) & NHẬT KÝ KIỂM TOÁN (REPORTING & AUDIT LOG)
==========================================================================================
Đáp ứng yêu cầu chức năng:
  - FR-33: Sinh báo cáo tổng hợp phân tích mô hình giao thông (TrafficPattern).
  - FR-34: Sinh báo cáo kết quả dự báo và so sánh các thực nghiệm (ForecastComparison).
  - FR-35: Kết xuất báo cáo tổng hợp định dạng PDF nhiều trang (ExecutiveSummary PDF).
  - FR-36: Kết xuất bảng số liệu CSV chuẩn UTF-8-SIG mở trực tiếp bằng Microsoft Excel.
  - FR-37: Ghi nhận và tra cứu nhật ký kiểm toán hệ thống (Audit Trail).

Bảng CSDL tương tác (Phân hệ 5 - UrbanTrafficAnalyticsDB):
  - Reports, AuditLogs, Users, TrafficAggregatedMetrics, Experiments, ForecastEvaluations
"""

import sqlite3
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "database" / "UrbanTrafficAnalyticsDB.db"
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Mở kết nối SQLite tới UrbanTrafficAnalyticsDB."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def write_audit_log(
    user_id: int | None,
    action_type: str,
    entity_name: str,
    entity_id: str,
    action_details: str,
    ip_address: str = "127.0.0.1",
    avoid_duplicate: bool = True,
    db_path: Path = DB_PATH,
) -> int:
    """
    FR-37: Ghi một bản ghi nhật ký kiểm toán vào bảng AuditLogs.
    Nếu `avoid_duplicate=True`, cập nhật thời gian nếu thao tác giống hệt vừa được ghi nhận.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()

    if avoid_duplicate:
        existing = cur.execute(
            """SELECT log_id FROM AuditLogs
               WHERE COALESCE(user_id, -1) = COALESCE(?, -1)
                 AND action_type = ? AND entity_name = ? AND action_details = ?""",
            (user_id, action_type, entity_name, action_details),
        ).fetchone()
        if existing:
            cur.execute(
                "UPDATE AuditLogs SET logged_at = datetime('now', 'localtime') WHERE log_id = ?",
                (existing[0],),
            )
            conn.commit()
            conn.close()
            return int(existing[0])

    cur.execute(
        """INSERT INTO AuditLogs (user_id, action_type, entity_name, entity_id, action_details, ip_address)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, action_type, entity_name, entity_id, action_details, ip_address),
    )
    log_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return log_id


def query_audit_logs(
    action_type: str | None = None,
    limit: int = 20,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    """FR-37: Truy vấn lịch sử nhật ký kiểm toán kèm tên người thực hiện."""
    conn = get_connection(db_path)
    where_sql = "WHERE a.action_type = ?" if action_type else ""
    params = (action_type, limit) if action_type else (limit,)
    sql = f"""
    SELECT
        a.log_id,
        COALESCE(u.username, 'system') AS nguoi_thuc_hien,
        a.action_type,
        a.entity_name,
        a.entity_id,
        a.action_details,
        a.ip_address,
        a.logged_at
    FROM AuditLogs a
    LEFT JOIN Users u ON a.user_id = u.user_id
    {where_sql}
    ORDER BY a.log_id DESC
    LIMIT ?
    """
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
    return df


def _upsert_report_record(
    experiment_id: int | None,
    report_type: str,
    file_format: str,
    rel_file_path: str,
    generated_by: int = 3,
    db_path: Path = DB_PATH,
) -> int:
    """Lưu hoặc cập nhật metadata file báo cáo vào bảng Reports (tránh sinh dòng trùng lặp)."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    existing = cur.execute(
        "SELECT report_id FROM Reports WHERE report_type = ? AND file_format = ? AND file_path = ?",
        (report_type, file_format, rel_file_path),
    ).fetchone()

    if existing:
        rep_id = int(existing[0])
        cur.execute(
            "UPDATE Reports SET generated_by = ?, generated_at = datetime('now', 'localtime') WHERE report_id = ?",
            (generated_by, rep_id),
        )
    else:
        cur.execute(
            """INSERT INTO Reports (experiment_id, report_type, file_format, file_path, generated_by)
               VALUES (?, ?, ?, ?, ?)""",
            (experiment_id, report_type, file_format, rel_file_path, generated_by),
        )
        rep_id = int(cur.lastrowid)

    conn.commit()
    conn.close()
    return rep_id


def export_traffic_pattern_csv(
    window_interval_sec: int = 30,
    generated_by: int = 3,
    output_dir: Path = OUTPUT_DIR,
    db_path: Path = DB_PATH,
) -> Path:
    """FR-33 & FR-36: Xuất báo cáo thống kê giao thông chuẩn CSV UTF-8-SIG (mở trực tiếp bằng Excel)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "M6_Bao_Cao_Phan_Tich_Giao_Thong.csv"

    conn = get_connection(db_path)
    df = pd.read_sql(
        """
        SELECT
            z.zone_name AS Khu_Vuc,
            m.window_interval_sec AS Khoang_Gop_Giay,
            m.window_start_time AS Bat_Dau,
            m.window_end_time AS Ket_Thuc,
            m.vehicle_count AS So_Phuong_Tien,
            m.avg_speed_kmh AS Van_Toc_TB_kmh,
            m.traffic_density_veh_km AS Mat_Do_xe_km,
            ROUND(m.traffic_density_veh_km * m.avg_speed_kmh, 2) AS Luu_Luong_xe_gio,
            m.is_peak_period AS La_Cao_Diem,
            m.congestion_level AS Muc_Un_Tac
        FROM TrafficAggregatedMetrics m
        JOIN TrafficSpatialZones z ON m.zone_id = z.zone_id
        WHERE m.window_interval_sec = ?
        ORDER BY z.zone_id, m.window_start_time
        """,
        conn,
        params=(window_interval_sec,),
    )
    conn.close()

    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    rel_path = str(out_path.relative_to(BASE_DIR))
    rep_id = _upsert_report_record(None, "TrafficPattern", "CSV", rel_path, generated_by, db_path)
    write_audit_log(
        generated_by,
        "EXPORT_REPORT",
        "Reports",
        str(rep_id),
        f"Kết xuất báo cáo giao thông CSV ({len(df)} dòng): {rel_path}",
        db_path=db_path,
    )
    return out_path


def export_forecast_comparison_csv(
    generated_by: int = 2,
    output_dir: Path = OUTPUT_DIR,
    db_path: Path = DB_PATH,
) -> Path:
    """FR-34 & FR-36: Xuất báo cáo tổng hợp kết quả dự báo & đánh giá thực nghiệm ra CSV/Excel."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "M6_Bao_Cao_So_Sanh_Du_Bao.csv"

    conn = get_connection(db_path)
    df = pd.read_sql(
        """
        SELECT
            e.experiment_id AS Ma_Thi_Nghiem,
            d.name AS Ten_Dataset,
            d.version_tag AS Phien_Ban,
            e.model_name AS Mo_Hinh,
            e.aggregation_interval_sec AS Khoang_Gop_Giay,
            e.train_ratio AS Ty_Le_Train,
            e.forecast_horizon_min AS Tam_Du_Bao_Phut,
            ev.mae AS MAE,
            ev.rmse AS RMSE,
            ev.mape AS MAPE_pct,
            ev.r_squared AS R2,
            e.hyperparameters AS Tham_So_Cau_Hinh
        FROM Experiments e
        JOIN ForecastEvaluations ev ON e.experiment_id = ev.experiment_id
        JOIN Datasets d ON e.dataset_id = d.dataset_id
        ORDER BY e.aggregation_interval_sec, ev.rmse ASC
        """,
        conn,
    )
    conn.close()

    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    best_exp_id = int(df["Ma_Thi_Nghiem"].iloc[0]) if not df.empty else None
    rel_path = str(out_path.relative_to(BASE_DIR))
    rep_id = _upsert_report_record(best_exp_id, "ForecastComparison", "CSV", rel_path, generated_by, db_path)
    write_audit_log(
        generated_by,
        "EXPORT_REPORT",
        "Reports",
        str(rep_id),
        f"Kết xuất báo cáo so sánh dự báo CSV ({len(df)} thực nghiệm): {rel_path}",
        db_path=db_path,
    )
    return out_path


def export_executive_summary_pdf(
    generated_by: int = 3,
    output_dir: Path = OUTPUT_DIR,
    db_path: Path = DB_PATH,
) -> Path:
    """
    FR-35: Kết xuất Báo cáo Tổng hợp định dạng PDF nhiều trang (ExecutiveSummary PDF)
    bằng PdfPages của matplotlib (tích hợp bảng số liệu thống kê + biểu đồ trực quan).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / "M6_Bao_Cao_Tong_Hop_Giao_Thong_Va_Du_Bao.pdf"

    conn = get_connection(db_path)
    df_zones = pd.read_sql(
        """
        SELECT
            z.zone_name AS Khu_Vuc,
            ROUND(AVG(m.vehicle_count), 1) AS So_Xe_TB,
            ROUND(AVG(m.avg_speed_kmh), 2) AS Van_Toc_TB_kmh,
            ROUND(AVG(m.traffic_density_veh_km), 2) AS Mat_Do_TB_xe_km,
            ROUND(MAX(m.traffic_density_veh_km), 2) AS Mat_Do_Max_xe_km,
            SUM(m.is_peak_period) AS So_Cao_Diem
        FROM TrafficAggregatedMetrics m
        JOIN TrafficSpatialZones z ON m.zone_id = z.zone_id
        WHERE m.window_interval_sec = 30
        GROUP BY z.zone_name
        ORDER BY Mat_Do_TB_xe_km DESC
        """,
        conn,
    )
    df_exp = pd.read_sql(
        """
        SELECT
            e.experiment_id AS ID,
            e.model_name AS Mo_Hinh,
            e.aggregation_interval_sec AS DT_Giay,
            ev.mae AS MAE,
            ev.rmse AS RMSE,
            ev.mape AS MAPE_pct
        FROM Experiments e
        JOIN ForecastEvaluations ev ON e.experiment_id = ev.experiment_id
        ORDER BY e.aggregation_interval_sec, ev.rmse ASC
        """,
        conn,
    )
    df_pts = pd.read_sql("SELECT x_pos, y_pos FROM TrajectoryPoints", conn)
    df_fc = pd.read_sql(
        """
        SELECT e.model_name, r.forecast_timestamp, r.actual_value, r.predicted_value
        FROM ForecastResults r JOIN Experiments e ON r.experiment_id = e.experiment_id
        WHERE e.aggregation_interval_sec = 15
        ORDER BY r.forecast_timestamp
        """,
        conn,
        parse_dates=["forecast_timestamp"],
    )
    conn.close()

    with PdfPages(pdf_path) as pdf:
        # --- TRANG 1: BẢNG SỐ LIỆU TỔNG HỢP GIAO THÔNG & ĐÁNH GIÁ DỰ BÁO ---
        fig1, axes1 = plt.subplots(2, 1, figsize=(11.69, 8.27))
        fig1.suptitle(
            "BÁO CÁO TỔNG HỢP PHÂN TÍCH MÔ HÌNH GIAO THÔNG & DỰ BÁO ÙN TẮC NGẮN HẠN (UAV pNEUMA)",
            fontsize=13,
            fontweight="bold",
            y=0.97,
        )

        axes1[0].axis("off")
        axes1[0].set_title("1. Bảng Thống kê Chỉ số Giao thông theo Khu vực (Cửa sổ Δt = 30s)", fontweight="bold", pad=8)
        tbl1 = axes1[0].table(
            cellText=df_zones.values,
            colLabels=df_zones.columns,
            loc="center",
            cellLoc="center",
        )
        tbl1.auto_set_font_size(False)
        tbl1.set_fontsize(9)
        tbl1.scale(1.0, 1.45)

        axes1[1].axis("off")
        axes1[1].set_title("2. Bảng Kết quả Đánh giá 9 Thực nghiệm Dự báo Ngắn hạn (Naive, ARIMA, Prophet)", fontweight="bold", pad=8)
        tbl2 = axes1[1].table(
            cellText=df_exp.values,
            colLabels=df_exp.columns,
            loc="center",
            cellLoc="center",
        )
        tbl2.auto_set_font_size(False)
        tbl2.set_fontsize(8.5)
        tbl2.scale(1.0, 1.32)

        plt.tight_layout(rect=[0, 0, 1, 0.94])
        pdf.savefig(fig1)
        plt.close(fig1)

        # --- TRANG 2: BIỂU ĐỒ TRỰC QUAN HÓA ĐIỂM NÓNG & ĐƯỜNG DỰ BÁO ---
        fig2, axes2 = plt.subplots(1, 2, figsize=(11.69, 6.2))
        fig2.suptitle("TRỰC QUAN HÓA ĐIỂM NÓNG KHÔNG GIAN & KẾT QUẢ DỰ BÁO NGẮN HẠN", fontsize=13, fontweight="bold")

        h = axes2[0].hist2d(df_pts["x_pos"], df_pts["y_pos"], bins=30, cmap="YlOrRd")
        plt.colorbar(h[3], ax=axes2[0], label="Số điểm phương tiện")
        axes2[0].set_title("Heatmap Điểm nóng Giao thông (TrajectoryPoints)")
        axes2[0].set_xlabel("Tọa độ X (m)")
        axes2[0].set_ylabel("Tọa độ Y (m)")

        if not df_fc.empty:
            m0 = df_fc["model_name"].iloc[0]
            sub0 = df_fc[df_fc["model_name"] == m0]
            axes2[1].plot(sub0["forecast_timestamp"], sub0["actual_value"], color="black", marker="o", lw=1.8, label="Thực tế")
            for m_name, grp in df_fc.groupby("model_name"):
                axes2[1].plot(grp["forecast_timestamp"], grp["predicted_value"], lw=1.6, label=f"Dự báo {m_name}")
        axes2[1].set_title("So sánh Đường Dự báo vs Thực tế tại Khu_Trung_Tam (Δt = 15s)")
        axes2[1].set_ylabel("Mật độ giao thông (xe/km)")
        axes2[1].tick_params(axis="x", rotation=25)
        axes2[1].legend(fontsize=8)

        plt.tight_layout(rect=[0, 0, 1, 0.93])
        pdf.savefig(fig2)
        plt.close(fig2)

    rel_path = str(pdf_path.relative_to(BASE_DIR))
    rep_id = _upsert_report_record(None, "ExecutiveSummary", "PDF", rel_path, generated_by, db_path)
    write_audit_log(
        generated_by,
        "EXPORT_REPORT",
        "Reports",
        str(rep_id),
        f"Kết xuất báo cáo tổng hợp PDF 2 trang: {rel_path}",
        db_path=db_path,
    )
    return pdf_path


def list_generated_reports(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Liệt kê toàn bộ danh sách file báo cáo đã được đăng ký trong bảng Reports."""
    conn = get_connection(db_path)
    df = pd.read_sql(
        """
        SELECT
            r.report_id,
            r.report_type,
            r.file_format,
            r.file_path,
            COALESCE(u.username, 'N/A') AS nguoi_xuat,
            r.generated_at
        FROM Reports r
        LEFT JOIN Users u ON r.generated_by = u.user_id
        ORDER BY r.report_id
        """,
        conn,
    )
    conn.close()
    return df


def run_demo() -> None:
    """Chạy kiểm thử độc lập toàn bộ chức năng Báo cáo & Audit Log của Module 6."""
    print("=" * 85)
    print("📄 MODULE 6 (M6): KẾT XUẤT BÁO CÁO (CSV / EXCEL / PDF) & NHẬT KÝ AUDIT LOG")
    print("=" * 85)

    csv_traffic = export_traffic_pattern_csv(window_interval_sec=30, generated_by=3, db_path=DB_PATH)
    csv_forecast = export_forecast_comparison_csv(generated_by=2, db_path=DB_PATH)
    pdf_summary = export_executive_summary_pdf(generated_by=3, db_path=DB_PATH)

    print("\n1️⃣ Đã kết xuất thành công 3 file báo cáo (FR-33, FR-34, FR-35, FR-36):")
    print(f"   • Báo cáo giao thông (CSV/Excel) : {csv_traffic}")
    print(f"   • Báo cáo dự báo (CSV/Excel)     : {csv_forecast}")
    print(f"   • Báo cáo tổng hợp 2 trang (PDF) : {pdf_summary}")

    print("\n2️⃣ Danh sách các báo cáo lưu trong bảng `Reports` của CSDL:")
    print(list_generated_reports(db_path=DB_PATH).to_string(index=False))

    print("\n3️⃣ Lịch sử nhật ký kiểm toán trong bảng `AuditLogs` (FR-37):")
    print(query_audit_logs(limit=15, db_path=DB_PATH).to_string(index=False))


if __name__ == "__main__":
    run_demo()
