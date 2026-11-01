"""
MODULE 3 (M3): DỰ BÁO ÙN TẮC NGẮN HẠN — NAIVE, ARIMA & PROPHET (FORECASTING MODULE)
===================================================================================
Đáp ứng yêu cầu chức năng & câu hỏi nghiên cứu (RQ2, RQ3, RQ4):
  - FR-18: Trích xuất chuỗi thời gian mật độ giao thông với nhiều khoảng gộp Δt (10s, 15s, 30s, 60s).
  - FR-19: Huấn luyện & dự báo bằng ARIMA (hỗ trợ cả chọn bậc (p,d,q) thủ công và auto chọn theo AIC).
  - FR-20: Huấn luyện & dự báo bằng Prophet (mô hình cộng tính Trend + Fourier Seasonality).
  - FR-21: Dự báo bằng mô hình chuẩn đối chiếu Naive Baseline (giá trị quan sát cuối cùng).
  - FR-22: Đánh giá độ chính xác bằng 4 chỉ số tiêu chuẩn: MAE, RMSE, MAPE (%), R².
  - FR-23: So sánh các mô hình trên cùng chuỗi thời gian và nhiều khoảng gộp Δt.
  - FR-24: Trực quan hóa đường thực tế vs dự báo kèm vùng khoảng tin cậy 95%.

Bảng CSDL tương tác (Phân hệ 3 & 4 - UrbanTrafficAnalyticsDB):
  - TrafficAggregatedMetrics, TrafficSpatialZones, Experiments, ForecastEvaluations, ForecastResults
"""

import sqlite3
import sys
import warnings
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

warnings.filterwarnings("ignore")
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


def extract_density_timeseries(
    zone_name: str = "Khu_Trung_Tam",
    window_interval_sec: int = 15,
    dataset_id: int = 1,
    db_path: Path = DB_PATH,
) -> pd.Series:
    """FR-18: Sinh chuỗi thời gian mật độ giao thông (xe/km) từ bảng TrafficAggregatedMetrics."""
    conn = get_connection(db_path)
    sql = """
    SELECT m.window_start_time, m.traffic_density_veh_km
    FROM TrafficAggregatedMetrics m
    JOIN TrafficSpatialZones z ON m.zone_id = z.zone_id
    WHERE m.dataset_id = ?
      AND z.zone_name = ?
      AND m.window_interval_sec = ?
    ORDER BY m.window_start_time
    """
    df = pd.read_sql(sql, conn, params=(dataset_id, zone_name, window_interval_sec), parse_dates=["window_start_time"])
    conn.close()
    if df.empty:
        raise ValueError(f"Không có dữ liệu chuỗi thời gian cho vùng '{zone_name}', Δt={window_interval_sec}s.")
    return df.set_index("window_start_time")["traffic_density_veh_km"]


def split_train_test(series: pd.Series, train_ratio: float = 0.80) -> tuple[pd.Series, pd.Series]:
    """Chia chuỗi thời gian theo đúng thứ tự quá khứ -> tương lai (mặc định 80% Train - 20% Test)."""
    n_total = len(series)
    n_test = max(5, int(round(n_total * (1.0 - train_ratio))))
    if n_test >= n_total:
        n_test = max(1, n_total // 5)
    return series.iloc[:-n_test], series.iloc[-n_test:]


def evaluate_forecast(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """FR-22: Tính 4 chỉ số đánh giá dự báo chuẩn: MAE, RMSE, MAPE (%) và R²."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = y_pred - y_true
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mape = float(np.mean(np.abs(err) / np.maximum(np.abs(y_true), 1.0)) * 100.0)
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1.0 - np.sum(err ** 2) / ss_tot) if ss_tot > 0 else 0.0
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 2),
        "r_squared": round(r2, 4),
    }


def forecast_naive_baseline(train_series: pd.Series, steps: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """FR-21: Dự báo bằng mô hình cơ sở Naive (giữ nguyên giá trị quan sát gần nhất)."""
    last_val = float(train_series.iloc[-1])
    pred = np.full(steps, last_val, dtype=float)
    diff_std = float(train_series.diff().dropna().std() or 1.0)
    lower = np.clip(pred - 1.96 * diff_std, 0.0, None)
    upper = pred + 1.96 * diff_std
    return pred, lower, upper, {"method": "last_value"}


def forecast_arima(
    train_series: pd.Series,
    steps: int,
    order: tuple[int, int, int] = (1, 0, 1),
    auto_order: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """
    FR-19: Huấn luyện và dự báo bằng mô hình ARIMA(p, d, q) của thư viện statsmodels.
    - Nếu `auto_order=False`: dùng đúng bậc `order` được truyền vào (mặc định (1,0,1) khớp CSDL).
    - Nếu `auto_order=True`: tự động duyệt lưới các bậc (p,d,q) và chọn mô hình có AIC nhỏ nhất.
    """
    y_train = train_series.to_numpy(dtype=float)

    if auto_order:
        candidates = [(1, 0, 1), (1, 1, 0), (0, 1, 1), (1, 1, 1), (2, 1, 1)]
        best_fit = None
        best_order = order
        best_aic = float("inf")
        for cand in candidates:
            try:
                fitted = ARIMA(y_train, order=cand).fit()
                if float(fitted.aic) < best_aic:
                    best_aic = float(fitted.aic)
                    best_fit = fitted
                    best_order = cand
            except Exception:
                continue
        arima_fit = best_fit if best_fit is not None else ARIMA(y_train, order=order).fit()
        chosen_order = best_order
    else:
        arima_fit = ARIMA(y_train, order=order).fit()
        chosen_order = order

    fc = arima_fit.get_forecast(steps=steps)
    pred = np.clip(np.asarray(fc.predicted_mean, dtype=float), 0.0, None)
    ci = np.asarray(fc.conf_int(alpha=0.05), dtype=float)
    lower = np.clip(ci[:, 0], 0.0, None)
    upper = ci[:, 1]
    hyper = {
        "p": int(chosen_order[0]),
        "d": int(chosen_order[1]),
        "q": int(chosen_order[2]),
        "aic": round(float(arima_fit.aic), 2),
    }
    return pred, lower, upper, hyper


def forecast_prophet(
    train_series: pd.Series,
    steps: int,
    interval_sec: int = 15,
    period_sec: float = 180.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """
    FR-20: Dự báo bằng mô hình cấu trúc cộng tính của Prophet:
           y(t) = Trend_tuyen_tinh(t) + Chu_ky_Fourier(t) + Sai_so
    Chu kỳ mặc định 180 giây (~3 phút) phản ánh nhịp pha đèn tín hiệu giao thông đô thị.
    """
    y = train_series.to_numpy(dtype=float)
    n = len(y)
    t = np.arange(n, dtype=float)
    period = max(6.0, float(period_sec) / float(interval_sec))

    X_train = np.column_stack([
        np.ones(n),
        t / n,
        np.sin(2.0 * np.pi * t / period),
        np.cos(2.0 * np.pi * t / period),
    ])
    coef, _, _, _ = np.linalg.lstsq(X_train, y, rcond=None)
    resid_std = float(np.std(y - X_train @ coef))

    t_fut = np.arange(n, n + steps, dtype=float)
    X_fut = np.column_stack([
        np.ones(steps),
        t_fut / n,
        np.sin(2.0 * np.pi * t_fut / period),
        np.cos(2.0 * np.pi * t_fut / period),
    ])
    pred = np.clip(X_fut @ coef, 0.0, None)
    lower = np.clip(pred - 1.96 * resid_std, 0.0, None)
    upper = pred + 1.96 * resid_std
    hyper = {"seasonality_mode": "additive", "period_sec": int(period_sec)}
    return pred, lower, upper, hyper


def compare_models_across_intervals(
    zone_name: str = "Khu_Trung_Tam",
    intervals: tuple[int, ...] = (10, 15, 30),
    train_ratio: float = 0.80,
    include_auto_arima: bool = True,
    dataset_id: int = 1,
    db_path: Path = DB_PATH,
) -> tuple[pd.DataFrame, dict]:
    """
    FR-23: Chạy và so sánh các mô hình dự báo trên nhiều khoảng gộp thời gian Δt (trả lời RQ2 & RQ3).
    Trả về (bảng kết quả đánh giá DataFrame, bộ nhớ đệm dữ liệu vẽ biểu đồ tại Δt=15s).
    """
    eval_rows = []
    plot_bundle = {}

    for interval_s in intervals:
        series = extract_density_timeseries(zone_name, interval_s, dataset_id, db_path)
        train_s, test_s = split_train_test(series, train_ratio=train_ratio)
        steps = len(test_s)

        outputs = {
            "Naive_Baseline": forecast_naive_baseline(train_s, steps),
            "ARIMA(1,0,1)": forecast_arima(train_s, steps, order=(1, 0, 1), auto_order=False),
            "Prophet": forecast_prophet(train_s, steps, interval_sec=interval_s, period_sec=180.0),
        }
        if include_auto_arima:
            outputs["ARIMA_Auto"] = forecast_arima(train_s, steps, auto_order=True)

        if interval_s == intervals[min(1, len(intervals) - 1)]:
            plot_bundle = {
                "zone_name": zone_name,
                "interval_sec": interval_s,
                "train": train_s,
                "test": test_s,
                "outputs": outputs,
            }

        for m_name, (pred_arr, _, _, hyper) in outputs.items():
            scores = evaluate_forecast(test_s.to_numpy(), pred_arr)
            eval_rows.append({
                "Khu_Vuc": zone_name,
                "Khoang_Gop_Giay": interval_s,
                "Mo_Hinh": m_name,
                "So_Mau_Train": len(train_s),
                "So_Buoc_Test": steps,
                "MAE": scores["mae"],
                "RMSE": scores["rmse"],
                "MAPE_pct": scores["mape"],
                "R2": scores["r_squared"],
                "Tham_So": str(hyper),
            })

    df_eval = pd.DataFrame(eval_rows).sort_values(["Khoang_Gop_Giay", "RMSE"]).reset_index(drop=True)
    return df_eval, plot_bundle


def plot_forecast_results(
    df_eval: pd.DataFrame,
    plot_bundle: dict,
    output_path: Path | None = None,
) -> Path:
    """FR-24: Vẽ biểu đồ thực tế vs dự báo kèm khoảng tin cậy 95% và biểu đồ so sánh RMSE."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = OUTPUT_DIR / "M3_du_bao_so_sanh_mo_hinh.png"

    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    train_s = plot_bundle["train"]
    test_s = plot_bundle["test"]
    interval_s = plot_bundle["interval_sec"]
    zone_name = plot_bundle["zone_name"]

    axes[0].plot(train_s.index, train_s.to_numpy(), color="#264653", lw=1.4, label="Huấn luyện (Train 80%)")
    axes[0].plot(test_s.index, test_s.to_numpy(), color="#000000", lw=2.0, marker="o", ms=4, label="Thực tế (Test 20%)")

    palette = {
        "Naive_Baseline": "#8d99ae",
        "ARIMA(1,0,1)": "#e76f51",
        "ARIMA_Auto": "#6a4c93",
        "Prophet": "#2a9d8f",
    }
    for m_name, (pred_arr, lo_arr, hi_arr, _) in plot_bundle["outputs"].items():
        col = palette.get(m_name, "#457b9d")
        axes[0].plot(test_s.index, pred_arr, lw=1.8, label=f"Dự báo {m_name}", color=col)
        if m_name in ("Prophet", "ARIMA_Auto"):
            axes[0].fill_between(test_s.index, lo_arr, hi_arr, color=col, alpha=0.14, label=f"KTC 95% ({m_name})")

    axes[0].axvline(test_s.index[0], color="grey", linestyle="--", lw=1.2)
    axes[0].set_title(f"1. Thực tế vs Dự báo mật độ tại {zone_name} (Δt = {interval_s}s)")
    axes[0].set_ylabel("Mật độ giao thông (xe/km)")
    axes[0].tick_params(axis="x", rotation=25)
    axes[0].legend(fontsize=8)

    model_cols = [c for c in ["Naive_Baseline", "ARIMA(1,0,1)", "ARIMA_Auto", "Prophet"]
                  if c in df_eval["Mo_Hinh"].unique()]
    piv_rmse = df_eval.pivot(index="Khoang_Gop_Giay", columns="Mo_Hinh", values="RMSE")[model_cols]
    bar_colors = [palette.get(c, "#457b9d") for c in model_cols]
    piv_rmse.plot.bar(ax=axes[1], color=bar_colors, rot=0, edgecolor="black")
    axes[1].set_title("2. So sánh sai số RMSE theo Khoảng gộp Δt (RQ2 & RQ3)")
    axes[1].set_xlabel("Khoảng gộp thời gian Δt (giây)")
    axes[1].set_ylabel("Sai số RMSE (xe/km)")
    axes[1].legend(title="Mô hình", fontsize=8)

    plt.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def run_demo() -> None:
    """Chạy kiểm thử độc lập toàn bộ chức năng dự báo của Module 3."""
    print("=" * 85)
    print("📈 MODULE 3 (M3): DỰ BÁO ÙN TẮC NGẮN HẠN — NAIVE, ARIMA & PROPHET")
    print("=" * 85)

    df_eval, plot_bundle = compare_models_across_intervals(
        zone_name="Khu_Trung_Tam",
        intervals=(10, 15, 30),
        train_ratio=0.80,
        include_auto_arima=True,
        db_path=DB_PATH,
    )
    print("\n1️⃣ Bảng đánh giá & so sánh độ chính xác dự báo (MAE, RMSE, MAPE, R²) tại Khu_Trung_Tam:")
    print(df_eval.to_string(index=False))

    saved_chart = plot_forecast_results(df_eval, plot_bundle)
    print(f"\n2️⃣ Đã vẽ và lưu biểu đồ trực quan hóa dự báo kèm khoảng tin cậy 95% (FR-24):")
    print(f"   • Đường dẫn ảnh: {saved_chart}")


if __name__ == "__main__":
    run_demo()
