"""
MODULE 5 (M5): QUẢN LÝ THỰC NGHIỆM & TÁI LẬP KẾT QUẢ (EXPERIMENT MANAGEMENT)
============================================================================
Đáp ứng yêu cầu chức năng & yêu cầu phi chức năng về tính tái lập (RQ2, RQ3):
  - FR-29: Tạo và thực thi thực nghiệm dự báo với cấu hình tùy chọn (dataset, vùng, Δt,
           mô hình, siêu tham số, tỉ lệ train/test, tầm dự báo, random_seed).
  - FR-30: Tự động đóng gói thông tin tái lập (phiên bản dataset, tham số mô hình, seed,
           phiên bản Python/pandas/numpy/statsmodels) lưu vào Experiments, ForecastEvaluations,
           ForecastResults.
  - FR-31: So sánh nhiều thực nghiệm bằng bảng xếp hạng, bảng Pivot RQ2/RQ3 và biểu đồ trực quan.
  - FR-32: Chạy lại một thực nghiệm bất kỳ từ cấu hình đã lưu trong CSDL và kiểm chứng kết quả
           trùng khớp tuyệt đối (|ΔRMSE| <= 1e-4).

Bảng CSDL tương tác (Phân hệ 4 - UrbanTrafficAnalyticsDB):
  - Experiments, ForecastEvaluations, ForecastResults, Datasets, AuditLogs
"""

import json
import platform
import sqlite3
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MODUL_DIR = Path(__file__).resolve().parent
if str(MODUL_DIR) not in sys.path:
    sys.path.insert(0, str(MODUL_DIR))

from M3_Du_bao_ngan_han import (
    evaluate_forecast,
    extract_density_timeseries,
    forecast_arima,
    forecast_naive_baseline,
    forecast_prophet,
    split_train_test,
)

BASE_DIR = MODUL_DIR.parent
DB_PATH = BASE_DIR / "database" / "UrbanTrafficAnalyticsDB.db"
OUTPUT_DIR = MODUL_DIR / "outputs"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Mở kết nối SQLite tới UrbanTrafficAnalyticsDB."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_and_run_experiment(
    model_name: str = "Prophet",
    aggregation_interval_sec: int = 15,
    zone_name: str = "Khu_Trung_Tam",
    dataset_id: int = 1,
    train_ratio: float = 0.80,
    forecast_horizon_min: int = 5,
    random_seed: int = 42,
    custom_params: dict | None = None,
    created_by: int = 2,
    db_path: Path = DB_PATH,
) -> dict:
    """
    FR-29 & FR-30: Khởi tạo thực nghiệm dự báo, tự động ghi nhận đầy đủ metadata tái lập
    và lưu kết quả vào 3 bảng Experiments, ForecastEvaluations, ForecastResults.
    """
    np.random.seed(random_seed)
    custom_params = custom_params or {}

    conn = get_connection(db_path)
    cur = conn.cursor()
    ds_row = cur.execute("SELECT version_tag FROM Datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()
    ds_version = str(ds_row[0]) if ds_row else "v1.0"
    conn.close()

    series = extract_density_timeseries(zone_name, aggregation_interval_sec, dataset_id, db_path)
    train_s, test_s = split_train_test(series, train_ratio=train_ratio)
    steps = len(test_s)

    if model_name == "Naive_Baseline":
        pred_arr, lo_arr, hi_arr, model_hyper = forecast_naive_baseline(train_s, steps)
    elif model_name == "ARIMA":
        order = (
            int(custom_params.get("p", 1)),
            int(custom_params.get("d", 0)),
            int(custom_params.get("q", 1)),
        )
        auto_flag = bool(custom_params.get("auto_order", False))
        pred_arr, lo_arr, hi_arr, model_hyper = forecast_arima(train_s, steps, order=order, auto_order=auto_flag)
    elif model_name == "Prophet":
        period_s = float(custom_params.get("period_sec", 180.0))
        pred_arr, lo_arr, hi_arr, model_hyper = forecast_prophet(
            train_s, steps, interval_sec=aggregation_interval_sec, period_sec=period_s
        )
    else:
        raise ValueError(f"Mô hình '{model_name}' chưa được hỗ trợ (chọn Naive_Baseline, ARIMA hoặc Prophet).")

    # Đóng gói đầy đủ thông tin tái lập theo chuẩn FR-30 & NFR-Reproducibility
    repro_metadata = {
        **model_hyper,
        "zone_name": zone_name,
        "dataset_version": ds_version,
        "env": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "statsmodels": statsmodels.__version__,
        },
    }
    scores = evaluate_forecast(test_s.to_numpy(), pred_arr)

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO Experiments
           (dataset_id, model_name, aggregation_interval_sec, hyperparameters,
            train_ratio, forecast_horizon_min, random_seed, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            dataset_id,
            model_name,
            aggregation_interval_sec,
            json.dumps(repro_metadata, ensure_ascii=False),
            train_ratio,
            forecast_horizon_min,
            random_seed,
            created_by,
        ),
    )
    exp_id = int(cur.lastrowid)

    cur.execute(
        """INSERT INTO ForecastEvaluations (experiment_id, mae, rmse, mape, r_squared)
           VALUES (?, ?, ?, ?, ?)""",
        (exp_id, scores["mae"], scores["rmse"], scores["mape"], scores["r_squared"]),
    )

    result_rows = [
        (
            exp_id,
            ts.strftime("%Y-%m-%d %H:%M:%S"),
            float(act),
            round(float(pr), 2),
            round(float(lo), 2),
            round(float(hi), 2),
        )
        for ts, act, pr, lo, hi in zip(test_s.index, test_s.to_numpy(), pred_arr, lo_arr, hi_arr)
    ]
    cur.executemany(
        """INSERT INTO ForecastResults
           (experiment_id, forecast_timestamp, actual_value, predicted_value, lower_bound, upper_bound)
           VALUES (?, ?, ?, ?, ?, ?)""",
        result_rows,
    )
    conn.commit()
    conn.close()

    return {
        "experiment_id": exp_id,
        "model_name": model_name,
        "interval_sec": aggregation_interval_sec,
        "zone_name": zone_name,
        "metrics": scores,
        "reproducibility_info": repro_metadata,
    }


def list_experiments(
    interval_sec: int | None = None,
    model_name: str | None = None,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    """FR-31: Truy vấn danh sách thực nghiệm kèm chỉ số MAE, RMSE, MAPE, R² và người tạo."""
    conn = get_connection(db_path)
    conds = []
    params = []
    if interval_sec is not None:
        conds.append("e.aggregation_interval_sec = ?")
        params.append(interval_sec)
    if model_name is not None:
        conds.append("e.model_name = ?")
        params.append(model_name)
    where_sql = ("WHERE " + " AND ".join(conds)) if conds else ""

    sql = f"""
    SELECT
        e.experiment_id,
        d.version_tag AS dataset_ver,
        e.model_name,
        e.aggregation_interval_sec AS dt_sec,
        e.train_ratio,
        e.random_seed AS seed,
        ev.mae,
        ev.rmse,
        ev.mape AS mape_pct,
        ev.r_squared AS r2,
        COALESCE(u.username, 'N/A') AS nguoi_tao
    FROM Experiments e
    JOIN ForecastEvaluations ev ON e.experiment_id = ev.experiment_id
    JOIN Datasets d ON e.dataset_id = d.dataset_id
    LEFT JOIN Users u ON e.created_by = u.user_id
    {where_sql}
    ORDER BY e.aggregation_interval_sec, ev.rmse ASC
    """
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
    return df


def pivot_experiments_rq2_rq3(db_path: Path = DB_PATH) -> pd.DataFrame:
    """FR-31: Tạo bảng đối chiếu chéo (Mô hình x Khoảng gộp Δt) theo RMSE để trả lời RQ2 & RQ3."""
    df = list_experiments(db_path=db_path)
    if df.empty:
        return df
    piv = (
        df.pivot_table(index="dt_sec", columns="model_name", values="rmse", aggfunc="min")
        .round(4)
        .reset_index()
        .rename(columns={"dt_sec": "Khoang_Gop_Giay"})
    )
    return piv


def reproduce_experiment(experiment_id: int, db_path: Path = DB_PATH) -> dict:
    """
    FR-32: Tái lập (chạy lại) một thực nghiệm đã lưu trong bảng Experiments từ cấu hình gốc
    và đối chiếu với chỉ số trong bảng ForecastEvaluations để chứng minh tính tái lập 100%.
    """
    conn = get_connection(db_path)
    sql = """
    SELECT
        e.experiment_id, e.dataset_id, e.model_name, e.aggregation_interval_sec,
        e.hyperparameters, e.train_ratio, e.random_seed,
        ev.mae AS stored_mae, ev.rmse AS stored_rmse, ev.mape AS stored_mape
    FROM Experiments e
    JOIN ForecastEvaluations ev ON e.experiment_id = ev.experiment_id
    WHERE e.experiment_id = ?
    """
    df = pd.read_sql(sql, conn, params=(experiment_id,))
    conn.close()

    if df.empty:
        return {"status": "NOT_FOUND", "message": f"Không tìm thấy experiment_id={experiment_id}"}

    row = df.iloc[0]
    hyper = json.loads(row["hyperparameters"]) if row["hyperparameters"] else {}
    zone_name = str(hyper.get("zone_name", "Khu_Trung_Tam"))
    seed = int(row["random_seed"]) if pd.notna(row["random_seed"]) else 42
    np.random.seed(seed)

    series = extract_density_timeseries(
        zone_name=zone_name,
        window_interval_sec=int(row["aggregation_interval_sec"]),
        dataset_id=int(row["dataset_id"]),
        db_path=db_path,
    )
    train_s, test_s = split_train_test(series, train_ratio=float(row["train_ratio"]))
    steps = len(test_s)

    m_name = str(row["model_name"])
    if m_name == "Naive_Baseline":
        pred_arr, _, _, _ = forecast_naive_baseline(train_s, steps)
    elif m_name == "ARIMA":
        order = (int(hyper.get("p", 1)), int(hyper.get("d", 0)), int(hyper.get("q", 1)))
        pred_arr, _, _, _ = forecast_arima(train_s, steps, order=order, auto_order=False)
    elif m_name == "Prophet":
        period_s = float(hyper.get("period_sec", 180.0))
        pred_arr, _, _, _ = forecast_prophet(
            train_s, steps, interval_sec=int(row["aggregation_interval_sec"]), period_sec=period_s
        )
    else:
        return {"status": "UNSUPPORTED_MODEL", "model_name": m_name}

    repro_scores = evaluate_forecast(test_s.to_numpy(), pred_arr)
    diff_rmse = abs(float(row["stored_rmse"]) - repro_scores["rmse"])
    diff_mae = abs(float(row["stored_mae"]) - repro_scores["mae"])
    is_exact = diff_rmse <= 1e-4 and diff_mae <= 1e-4

    return {
        "experiment_id": int(experiment_id),
        "model_name": m_name,
        "dt_sec": int(row["aggregation_interval_sec"]),
        "stored_rmse": float(row["stored_rmse"]),
        "reproduced_rmse": repro_scores["rmse"],
        "abs_diff_rmse": round(diff_rmse, 6),
        "is_reproducible": is_exact,
        "verdict": "✅ Trùng khớp 100%" if is_exact else "⚠️ Có sai lệch",
    }


def plot_experiment_comparison(output_path: Path | None = None, db_path: Path = DB_PATH) -> Path:
    """FR-31: Vẽ biểu đồ so sánh MAE và MAPE (%) của tất cả các thực nghiệm trong CSDL."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if output_path is None:
        output_path = OUTPUT_DIR / "M5_so_sanh_thuc_nghiem.png"

    df = list_experiments(db_path=db_path)
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8))

    piv_mae = df.pivot_table(index="dt_sec", columns="model_name", values="mae", aggfunc="min")
    piv_mape = df.pivot_table(index="dt_sec", columns="model_name", values="mape_pct", aggfunc="min")

    cols = [c for c in ["Naive_Baseline", "ARIMA", "Prophet"] if c in piv_mae.columns]
    colors = ["#8d99ae", "#e76f51", "#2a9d8f"][: len(cols)]

    piv_mae[cols].plot.bar(ax=axes[0], color=colors, rot=0, edgecolor="black")
    axes[0].set_title("1. So sánh sai số MAE (xe/km) giữa các thực nghiệm")
    axes[0].set_xlabel("Khoảng gộp thời gian Δt (giây)")
    axes[0].set_ylabel("MAE (xe/km)")

    piv_mape[cols].plot.bar(ax=axes[1], color=colors, rot=0, edgecolor="black")
    axes[1].set_title("2. So sánh sai số tương đối MAPE (%) giữa các thực nghiệm")
    axes[1].set_xlabel("Khoảng gộp thời gian Δt (giây)")
    axes[1].set_ylabel("MAPE (%)")

    plt.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def run_demo() -> None:
    """Chạy kiểm thử độc lập toàn bộ chức năng quản lý & tái lập thực nghiệm của Module 5."""
    print("=" * 85)
    print("🧪 MODULE 5 (M5): QUẢN LÝ THỰC NGHIỆM & KIỂM CHỨNG TÍNH TÁI LẬP (Reproducibility)")
    print("=" * 85)

    print("\n1️⃣ Danh sách 9 thực nghiệm chuẩn đang lưu trong CSDL (FR-31):")
    print(list_experiments(db_path=DB_PATH).to_string(index=False))

    print("\n2️⃣ Bảng Pivot đối chiếu RMSE theo (Khoảng gộp Δt × Mô hình) trả lời RQ2 & RQ3:")
    print(pivot_experiments_rq2_rq3(db_path=DB_PATH).to_string(index=False))

    print("\n3️⃣ Kiểm chứng chạy lại (Reproduce) các thực nghiệm đã lưu trong CSDL (FR-32):")
    repro_rows = [reproduce_experiment(eid, db_path=DB_PATH) for eid in (1, 2, 3, 4, 6, 9)]
    print(pd.DataFrame(repro_rows).to_string(index=False))

    print("\n4️⃣ Minh họa tạo thực nghiệm mới ARIMA(1,1,1) có lưu đầy đủ phiên bản môi trường (FR-29, FR-30):")
    new_exp = create_and_run_experiment(
        model_name="ARIMA",
        aggregation_interval_sec=15,
        zone_name="Khu_Trung_Tam",
        custom_params={"p": 1, "d": 1, "q": 1},
        random_seed=42,
        created_by=2,
        db_path=DB_PATH,
    )
    new_id = new_exp["experiment_id"]
    print(f"   • Đã tạo experiment_id={new_id} | Metrics={new_exp['metrics']}")
    print(f"   • Metadata tái lập tự động lưu: {new_exp['reproducibility_info']}")
    print(f"   • Kiểm tra tái lập ngay trên experiment_id={new_id}: {reproduce_experiment(new_id, DB_PATH)['verdict']}")

    # Dọn bản ghi thử nghiệm tạm thời để bảo toàn 9 thực nghiệm chuẩn của bộ bài nộp
    conn = get_connection(DB_PATH)
    conn.execute("DELETE FROM Experiments WHERE experiment_id = ?", (new_id,))
    conn.execute("UPDATE sqlite_sequence SET seq = (SELECT MAX(experiment_id) FROM Experiments) WHERE name = 'Experiments'")
    conn.execute("UPDATE sqlite_sequence SET seq = (SELECT MAX(eval_id) FROM ForecastEvaluations) WHERE name = 'ForecastEvaluations'")
    conn.execute("UPDATE sqlite_sequence SET seq = (SELECT MAX(result_id) FROM ForecastResults) WHERE name = 'ForecastResults'")
    conn.commit()
    conn.close()

    chart_path = plot_experiment_comparison(db_path=DB_PATH)
    print(f"\n5️⃣ Đã xuất biểu đồ so sánh các thực nghiệm tại: {chart_path}")


if __name__ == "__main__":
    run_demo()
