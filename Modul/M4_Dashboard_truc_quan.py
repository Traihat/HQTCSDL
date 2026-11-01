"""
MODULE 4 (M4): DASHBOARD TRỰC QUAN HÓA GIAO THÔNG & DỰ BÁO (VISUALIZATION DASHBOARD)
====================================================================================
Đáp ứng yêu cầu chức năng & câu hỏi nghiên cứu (RQ4):
  - FR-25: Biểu đồ chuỗi thời gian xu hướng mật độ, vận tốc và điểm cao điểm (is_peak_period).
  - FR-26: Bản đồ nhiệt không gian (Spatial Heatmap) kèm ranh giới các vùng TrafficSpatialZones.
  - FR-27: Biểu đồ phân phối vận tốc (Histogram) và tỷ lệ cơ cấu loại phương tiện / mức ùn tắc.
  - FR-28: Bảng tổng quan các chỉ số KPI cốt lõi của toàn hệ thống.
  - FR-38: Bảng trợ giúp & giải thích ý nghĩa các chỉ số giao thông / dự báo (Online Glossary).

Bảng CSDL tương tác (Toàn bộ dữ liệu phân tích & dự báo trong UrbanTrafficAnalyticsDB):
  - Datasets, Tracks, TrajectoryPoints, TrafficSpatialZones, TrafficAggregatedMetrics,
    Experiments, ForecastEvaluations, ForecastResults
"""

import sqlite3
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
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


def get_dashboard_kpis(window_interval_sec: int = 30, db_path: Path = DB_PATH) -> pd.DataFrame:
    """FR-28: Truy vấn SQL tổng hợp bảng chỉ số KPI trung tâm trên Dashboard."""
    conn = get_connection(db_path)
    kpi_sql = """
    SELECT
        (SELECT COUNT(*) FROM Datasets WHERE status != 'Archived') AS Tong_Dataset_Hoat_Dong,
        (SELECT COUNT(*) FROM Tracks) AS Tong_Phuong_Tien_Da_Lam_Sach,
        (SELECT COUNT(*) FROM TrajectoryPoints) AS Tong_Diem_Quy_Dao_DB,
        (SELECT ROUND(AVG(avg_speed_kmh), 2)
         FROM TrafficAggregatedMetrics WHERE window_interval_sec = ? AND vehicle_count > 0) AS Van_Toc_TB_kmh,
        (SELECT ROUND(AVG(traffic_density_veh_km), 2)
         FROM TrafficAggregatedMetrics WHERE window_interval_sec = ?) AS Mat_Do_TB_xe_km,
        (SELECT ROUND(MAX(traffic_density_veh_km), 2)
         FROM TrafficAggregatedMetrics WHERE window_interval_sec = ?) AS Mat_Do_Cuc_Dai_xe_km,
        (SELECT SUM(is_peak_period)
         FROM TrafficAggregatedMetrics WHERE window_interval_sec = ?) AS So_Khoang_Cao_Diem,
        (SELECT congestion_level
         FROM TrafficAggregatedMetrics WHERE window_interval_sec = ?
         GROUP BY congestion_level ORDER BY COUNT(*) DESC LIMIT 1) AS Muc_Un_Tac_Pho_Bien_Nhat,
        (SELECT COUNT(*) FROM Experiments) AS Tong_So_Thi_Nghiem_Du_Bao,
        (SELECT e.model_name || ' @ ' || e.aggregation_interval_sec || 's (RMSE=' || ev.rmse || ')'
         FROM Experiments e JOIN ForecastEvaluations ev ON e.experiment_id = ev.experiment_id
         ORDER BY ev.rmse ASC LIMIT 1) AS Mo_Hinh_Du_Bao_Tot_Nhat
    """
    params = (
        window_interval_sec,
        window_interval_sec,
        window_interval_sec,
        window_interval_sec,
        window_interval_sec,
    )
    raw_df = pd.read_sql(kpi_sql, conn, params=params)
    conn.close()

    labels = {
        "Tong_Dataset_Hoat_Dong": "1. Số bộ dữ liệu UAV đang hoạt động",
        "Tong_Phuong_Tien_Da_Lam_Sach": "2. Tổng số phương tiện cơ giới đã làm sạch (xe)",
        "Tong_Diem_Quy_Dao_DB": "3. Số điểm tọa độ quỹ đạo lưu trong CSDL (điểm)",
        "Van_Toc_TB_kmh": f"4. Vận tốc trung bình toàn mạng lưới @ {window_interval_sec}s (km/h)",
        "Mat_Do_TB_xe_km": f"5. Mật độ giao thông trung bình @ {window_interval_sec}s (xe/km)",
        "Mat_Do_Cuc_Dai_xe_km": f"6. Mật độ giao thông cực đại @ {window_interval_sec}s (xe/km)",
        "So_Khoang_Cao_Diem": f"7. Tổng số khung thời gian cao điểm @ {window_interval_sec}s",
        "Muc_Un_Tac_Pho_Bien_Nhat": "8. Trạng thái dòng giao thông phổ biến nhất",
        "Tong_So_Thi_Nghiem_Du_Bao": "9. Tổng số thực nghiệm dự báo đã lưu trong CSDL",
        "Mo_Hinh_Du_Bao_Tot_Nhat": "10. Cấu hình dự báo có sai số RMSE thấp nhất",
    }
    rows = [{"Chỉ số KPI tổng quan": labels.get(col, col), "Giá trị": raw_df[col].iloc[0]} for col in raw_df.columns]
    return pd.DataFrame(rows)


def get_online_help_glossary() -> pd.DataFrame:
    """FR-38: Trợ giúp trực tuyến giải thích công thức và cách đọc các chỉ số trên Dashboard."""
    items = [
        ("Mật độ (traffic_density_veh_km)", "Số xe hiện diện trung bình trên 1 km chiều dài đường (xe/km)."),
        ("Vận tốc TB (avg_speed_kmh)", "Vận tốc tức thời trung bình của các xe trong khung thời gian Δt (km/h)."),
        ("Lưu lượng (q = k × v)", "Số lượng phương tiện thông qua mặt cắt đường quy đổi theo giờ (xe/giờ)."),
        ("Cao điểm (is_peak_period = 1)", "Khung thời gian thuộc nhóm Top 20% mật độ giao thông cao nhất của vùng."),
        ("4 Mức ùn tắc (Congestion Level)", "Free Flow (≥22 km/h), Moderate (15–22), Heavy (10–15), Gridlock (<10 km/h)."),
        ("MAE & RMSE", "Sai số tuyệt đối TB và Căn bậc hai sai số toàn phương TB (càng nhỏ càng chính xác)."),
        ("MAPE (%)", "Sai số phần trăm tuyệt đối trung bình (<10%: dự báo độ chính xác rất cao)."),
    ]
    return pd.DataFrame(items, columns=["Thuật ngữ / Chỉ số", "Giải thích ý nghĩa & Cách đọc trên Dashboard"])


def plot_spatial_heatmap(bins: int = 35, output_path: Path | None = None, db_path: Path = DB_PATH) -> Path:
    """FR-26: Vẽ Heatmap mật độ phương tiện 2D kèm đường bao 5 vùng không gian TrafficSpatialZones."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = OUTPUT_DIR / "M4_heatmap_khong_gian_va_vung.png"

    conn = get_connection(db_path)
    pts = pd.read_sql("SELECT x_pos, y_pos, speed_ms * 3.6 AS speed_kmh FROM TrajectoryPoints", conn)
    zones = pd.read_sql(
        "SELECT zone_name, x_min, x_max, y_min, y_max FROM TrafficSpatialZones WHERE zone_name != 'Toan_Khu_Vuc'",
        conn,
    )
    conn.close()

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))

    # Ô trái: Heatmap mật độ số điểm quỹ đạo
    h = axes[0].hist2d(pts["x_pos"], pts["y_pos"], bins=bins, cmap="YlOrRd")
    plt.colorbar(h[3], ax=axes[0], label="Mật độ điểm phương tiện")
    for _, z in zones.iterrows():
        rect = Rectangle(
            (z["x_min"], z["y_min"]),
            z["x_max"] - z["x_min"],
            z["y_max"] - z["y_min"],
            fill=False,
            edgecolor="#1d3557",
            lw=1.8,
            linestyle="--",
        )
        axes[0].add_patch(rect)
        axes[0].text(
            0.5 * (z["x_min"] + z["x_max"]),
            0.5 * (z["y_min"] + z["y_max"]),
            str(z["zone_name"]),
            fontsize=8,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.8),
        )
    axes[0].set_title("1. Heatmap Mật độ Không gian & Ranh giới 5 Vùng")
    axes[0].set_xlabel("Tọa độ X - Đông Tây (m)")
    axes[0].set_ylabel("Tọa độ Y - Nam Bắc (m)")

    # Ô phải: Bản đồ phân bố điểm xe theo dải vận tốc (nhận diện trực quan vùng đi chậm)
    sc = axes[1].scatter(
        pts["x_pos"].iloc[::3],
        pts["y_pos"].iloc[::3],
        c=pts["speed_kmh"].iloc[::3],
        cmap="RdYlGn",
        s=3,
        alpha=0.65,
        vmin=0,
        vmax=55,
    )
    plt.colorbar(sc, ax=axes[1], label="Vận tốc phương tiện (km/h)")
    axes[1].set_title("2. Bản đồ Vận tốc Không gian (Đỏ = Ùn tắc chậm, Xanh = Thông thoáng)")
    axes[1].set_xlabel("Tọa độ X - Đông Tây (m)")
    axes[1].set_ylabel("Tọa độ Y - Nam Bắc (m)")

    plt.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def generate_full_dashboard(output_path: Path | None = None, db_path: Path = DB_PATH) -> Path:
    """
    FR-25, FR-26, FR-27, FR-28: Kết xuất Dashboard tổng hợp 6 biểu đồ (2 hàng x 3 cột)
    kết nối trực tiếp từ các bảng SQL của UrbanTrafficAnalyticsDB.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = OUTPUT_DIR / "M4_dashboard_tong_quan_6_bieu_do.png"

    conn = get_connection(db_path)
    df_ts = pd.read_sql(
        """
        SELECT m.window_start_time, z.zone_name, m.avg_speed_kmh, m.traffic_density_veh_km, m.is_peak_period
        FROM TrafficAggregatedMetrics m
        JOIN TrafficSpatialZones z ON m.zone_id = z.zone_id
        WHERE m.window_interval_sec = 15 AND z.zone_name != 'Toan_Khu_Vuc'
        ORDER BY m.window_start_time
        """,
        conn,
        parse_dates=["window_start_time"],
    )
    df_pts = pd.read_sql("SELECT x_pos, y_pos, speed_ms * 3.6 AS speed_kmh FROM TrajectoryPoints", conn)
    df_veh = pd.read_sql(
        "SELECT vehicle_type, COUNT(*) AS so_xe FROM Tracks GROUP BY vehicle_type ORDER BY so_xe ASC",
        conn,
    )
    df_cong = pd.read_sql(
        """
        SELECT z.zone_name, m.congestion_level, COUNT(*) AS cnt
        FROM TrafficAggregatedMetrics m JOIN TrafficSpatialZones z ON m.zone_id = z.zone_id
        WHERE m.window_interval_sec = 15 AND z.zone_name != 'Toan_Khu_Vuc'
        GROUP BY z.zone_name, m.congestion_level
        """,
        conn,
    )
    df_fc = pd.read_sql(
        """
        SELECT e.model_name, r.forecast_timestamp, r.actual_value, r.predicted_value, r.lower_bound, r.upper_bound
        FROM ForecastResults r
        JOIN Experiments e ON r.experiment_id = e.experiment_id
        WHERE e.aggregation_interval_sec = 15
        ORDER BY r.forecast_timestamp
        """,
        conn,
        parse_dates=["forecast_timestamp"],
    )
    conn.close()

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    # Ô (0, 0): Chuỗi thời gian mật độ theo vùng + Cao điểm (FR-25)
    for zn, grp in df_ts.groupby("zone_name"):
        axes[0, 0].plot(grp["window_start_time"], grp["traffic_density_veh_km"], lw=1.4, label=zn)
    peaks = df_ts[df_ts["is_peak_period"] == 1]
    axes[0, 0].scatter(
        peaks["window_start_time"],
        peaks["traffic_density_veh_km"],
        facecolors="none",
        edgecolors="red",
        s=35,
        label="Cao điểm",
    )
    axes[0, 0].set_title("(1) Xu hướng mật độ & Điểm cao điểm (Δt = 15s)")
    axes[0, 0].set_ylabel("Mật độ (xe/km)")
    axes[0, 0].tick_params(axis="x", rotation=25)
    axes[0, 0].legend(fontsize=7)

    # Ô (0, 1): Chuỗi thời gian vận tốc trung bình theo vùng (FR-25)
    for zn, grp in df_ts.groupby("zone_name"):
        axes[0, 1].plot(grp["window_start_time"], grp["avg_speed_kmh"], lw=1.4, label=zn)
    axes[0, 1].axhline(15.0, color="#e76f51", linestyle="--", lw=1.1, label="Ngưỡng Heavy (15 km/h)")
    axes[0, 1].set_title("(2) Biến thiên vận tốc trung bình theo vùng (km/h)")
    axes[0, 1].set_ylabel("Vận tốc TB (km/h)")
    axes[0, 1].tick_params(axis="x", rotation=25)
    axes[0, 1].legend(fontsize=7)

    # Ô (0, 2): Heatmap không gian điểm nóng giao thông (FR-26)
    h = axes[0, 2].hist2d(df_pts["x_pos"], df_pts["y_pos"], bins=30, cmap="YlOrRd")
    plt.colorbar(h[3], ax=axes[0, 2], label="Số điểm xe")
    axes[0, 2].set_title("(3) Heatmap Điểm nóng không gian (TrajectoryPoints)")
    axes[0, 2].set_xlabel("X (m)")
    axes[0, 2].set_ylabel("Y (m)")

    # Ô (1, 0): Histogram phân phối vận tốc (FR-27)
    axes[1, 0].hist(df_pts["speed_kmh"], bins=35, color="#457b9d", edgecolor="white")
    med_v = float(df_pts["speed_kmh"].median())
    mean_v = float(df_pts["speed_kmh"].mean())
    axes[1, 0].axvline(med_v, color="#e63946", linestyle="--", lw=1.6, label=f"Trung vị: {med_v:.1f} km/h")
    axes[1, 0].axvline(mean_v, color="#ffb703", linestyle="-", lw=1.6, label=f"Trung bình: {mean_v:.1f} km/h")
    axes[1, 0].set_title("(4) Phân phối vận tốc phương tiện (Histogram)")
    axes[1, 0].set_xlabel("Vận tốc (km/h)")
    axes[1, 0].set_ylabel("Số điểm quỹ đạo")
    axes[1, 0].legend(fontsize=8)

    # Ô (1, 1): Tỷ lệ 4 mức độ ùn tắc theo khu vực (FR-27)
    piv_c = (
        df_cong.pivot(index="zone_name", columns="congestion_level", values="cnt")
        .fillna(0)
        .reindex(columns=["Free Flow", "Moderate", "Heavy", "Gridlock"], fill_value=0)
    )
    piv_pct = piv_c.div(piv_c.sum(axis=1).replace(0, 1), axis=0).mul(100.0)
    piv_pct.plot.barh(stacked=True, ax=axes[1, 1], color=["#2a9d8f", "#e9c46a", "#f4a261", "#e76f51"])
    axes[1, 1].set_title("(5) Tỷ lệ mức độ ùn tắc (%) theo từng vùng")
    axes[1, 1].set_xlabel("Tỷ lệ (%)")
    axes[1, 1].legend(fontsize=7, loc="lower right")

    # Ô (1, 2): Kết quả dự báo ngắn hạn từ bảng ForecastResults (FR-24 / Dashboard)
    if not df_fc.empty:
        first_model = df_fc["model_name"].iloc[0]
        actual_sub = df_fc[df_fc["model_name"] == first_model]
        axes[1, 2].plot(
            actual_sub["forecast_timestamp"],
            actual_sub["actual_value"],
            color="black",
            marker="o",
            ms=4,
            lw=1.8,
            label="Thực tế",
        )
        m_colors = {"Naive_Baseline": "#8d99ae", "ARIMA": "#e76f51", "Prophet": "#2a9d8f"}
        for m_name, grp in df_fc.groupby("model_name"):
            c = m_colors.get(m_name, "#6a4c93")
            axes[1, 2].plot(grp["forecast_timestamp"], grp["predicted_value"], lw=1.6, label=m_name, color=c)
            if m_name == "Prophet":
                axes[1, 2].fill_between(
                    grp["forecast_timestamp"], grp["lower_bound"], grp["upper_bound"], color=c, alpha=0.15
                )
    else:
        axes[1, 2].barh(df_veh["vehicle_type"], df_veh["so_xe"], color="#2a9d8f")
    axes[1, 2].set_title("(6) Dự báo mật độ vs Thực tế @ Δt = 15s (ForecastResults)")
    axes[1, 2].set_ylabel("Mật độ (xe/km)")
    axes[1, 2].tick_params(axis="x", rotation=25)
    axes[1, 2].legend(fontsize=8)

    fig.suptitle(
        "DASHBOARD TRỰC QUAN HÓA PHÂN TÍCH & DỰ BÁO GIAO THÔNG ĐÔ THỊ (UrbanTrafficAnalyticsDB)",
        fontsize=14,
        fontweight="bold",
    )
    plt.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def run_demo() -> None:
    """Chạy kiểm thử độc lập toàn bộ chức năng Dashboard của Module 4."""
    print("=" * 85)
    print("🖥️ MODULE 4 (M4): DASHBOARD TRỰC QUAN HÓA GIAO THÔNG & CHỈ SỐ KPI")
    print("=" * 85)

    print("\n1️⃣ Bảng chỉ số KPI tổng quan của toàn hệ thống (FR-28):")
    print(get_dashboard_kpis(window_interval_sec=30, db_path=DB_PATH).to_string(index=False))

    print("\n2️⃣ Bảng trợ giúp trực tuyến giải thích các chỉ số trên Dashboard (FR-38):")
    print(get_online_help_glossary().to_string(index=False))

    dash_img = generate_full_dashboard(db_path=DB_PATH)
    heat_img = plot_spatial_heatmap(db_path=DB_PATH)
    print("\n3️⃣ Đã sinh thành công các biểu đồ Dashboard trực quan (FR-25, FR-26, FR-27):")
    print(f"   • Dashboard 6 biểu đồ tổng hợp : {dash_img}")
    print(f"   • Heatmap mật độ & vận tốc 2D  : {heat_img}")


if __name__ == "__main__":
    run_demo()
