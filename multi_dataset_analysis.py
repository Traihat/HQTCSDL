"""Time-series aggregation and forecasting across explicitly selected datasets."""

import json
import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from db_manager import DB_PATH, get_connection, init_db
from module3_forecasting import (
    _calc_metrics,
    _fit_predict_arima,
    _fit_predict_prophet,
)

ALLOWED_INTERVALS = {5, 15}
ALLOWED_METRICS = {"vehicle_count", "avg_speed_kmh", "traffic_flow_veh_h"}


def _validate_selection(dataset_ids: list[int], interval_minutes: int, metric: str) -> list[int]:
    if not isinstance(dataset_ids, list) or not dataset_ids:
        raise ValueError("Chọn ít nhất một Dataset.")
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in dataset_ids):
        raise ValueError("Danh sách Dataset ID không hợp lệ.")
    selected_ids = list(dict.fromkeys(dataset_ids))
    if interval_minutes not in ALLOWED_INTERVALS:
        raise ValueError("Khoảng tổng hợp chỉ hỗ trợ 5 hoặc 15 phút.")
    if metric not in ALLOWED_METRICS:
        raise ValueError("Chỉ số dự báo không được hỗ trợ.")
    return selected_ids


def _build_series(
    dataset_ids: list[int],
    interval_minutes: int,
    target_metric: str,
    db_path: Path,
) -> dict:
    selected_ids = _validate_selection(dataset_ids, interval_minutes, target_metric)
    init_db(db_path)
    placeholders = ",".join("?" for _ in selected_ids)
    conn = get_connection(db_path)
    datasets = conn.execute(
        f"""
        SELECT import_id, file_name, cleaned_row_count, processing_status
        FROM DatasetImports
        WHERE import_id IN ({placeholders}) AND is_deleted = 0
        ORDER BY import_id
        """,
        selected_ids,
    ).fetchall()
    if len(datasets) != len(selected_ids):
        conn.close()
        raise ValueError("Một hoặc nhiều Dataset không tồn tại, đã lưu trữ hoặc không được chọn.")
    invalid = [row[1] for row in datasets if row[3] != "saved"]
    if invalid:
        conn.close()
        raise ValueError("Dataset chưa ở trạng thái sẵn sàng: " + ", ".join(invalid))

    time_ranges = conn.execute(
        f"""
        SELECT import_id, MIN(datetime(recorded_time_str)), MAX(datetime(recorded_time_str))
        FROM CleanedTrajectories
        WHERE import_id IN ({placeholders})
        GROUP BY import_id
        """,
        selected_ids,
    ).fetchall()
    if len(time_ranges) != len(selected_ids):
        conn.close()
        raise ValueError("Có Dataset không chứa timestamp quỹ đạo hợp lệ.")

    range_by_id = {
        int(row[0]): (datetime.fromisoformat(row[1]), datetime.fromisoformat(row[2]))
        for row in time_ranges
    }
    ordered_ranges = sorted(
        ((range_by_id[dataset_id][0], range_by_id[dataset_id][1], dataset_id) for dataset_id in selected_ids),
        key=lambda item: item[0],
    )
    for previous, current in zip(ordered_ranges, ordered_ranges[1:]):
        if current[0] <= previous[1]:
            previous_name = next(row[1] for row in datasets if row[0] == previous[2])
            current_name = next(row[1] for row in datasets if row[0] == current[2])
            conn.close()
            raise ValueError(
                f"Khoảng thời gian của {previous_name} và {current_name} chồng lấn. "
                "Không thể cộng dữ liệu khi chưa có quy tắc khử trùng phương tiện đa drone."
            )

    bucket = (
        "strftime('%Y-%m-%d %H:', t.recorded_time_str) || "
        "printf('%02d', (CAST(strftime('%M', t.recorded_time_str) AS INTEGER) / ?) * ?) || ':00'"
    )
    rows = conn.execute(
        f"""
        SELECT {bucket} AS bucket_time,
               COUNT(DISTINCT CAST(t.import_id AS TEXT) || ':' || t.vehicle_id) AS vehicle_count,
               AVG(t.speed_kmh) AS avg_speed_kmh,
               AVG(t.accel_ms2) AS avg_accel_ms2,
               COUNT(*) AS record_count
        FROM CleanedTrajectories t
        WHERE t.import_id IN ({placeholders})
          AND datetime(t.recorded_time_str) IS NOT NULL
        GROUP BY bucket_time
        ORDER BY bucket_time
        """,
        [interval_minutes, interval_minutes, *selected_ids],
    ).fetchall()
    conn.close()
    if not rows:
        raise ValueError("Không tạo được chuỗi thời gian từ các Dataset đã chọn.")

    series = []
    for row in rows:
        vehicle_count = int(row[1])
        series.append({
            "timestamp": row[0],
            "vehicle_count": vehicle_count,
            "avg_speed_kmh": round(float(row[2]), 4),
            "traffic_flow_veh_h": round(vehicle_count * 60.0 / interval_minutes, 4),
            "avg_acceleration_ms2": round(float(row[3]), 4),
            "record_count": int(row[4]),
        })

    start = datetime.fromisoformat(series[0]["timestamp"])
    end = datetime.fromisoformat(series[-1]["timestamp"])
    expected_bins = int((end - start).total_seconds() // (interval_minutes * 60)) + 1
    missing_count = max(0, expected_bins - len(series))
    summary = {
        "dataset_ids": selected_ids,
        "dataset_count": len(selected_ids),
        "total_record_count": sum(int(row[2]) for row in datasets),
        "series_count": len(series),
        "training_start": series[0]["timestamp"],
        "training_end": series[-1]["timestamp"],
        "interval_minutes": interval_minutes,
        "target_metric": target_metric,
        "missing_timestamp_count": missing_count,
        "missing_timestamps_filled": False,
        "overlapping_time_ranges": False,
        "eligible_for_forecasting": missing_count == 0 and len(series) >= 12,
    }
    return {"summary": summary, "series": series}


def _persist_analysis(
    aggregation: dict,
    dataset_ids: list[int],
    interval_minutes: int,
    target_metric: str,
    db_path: Path,
) -> int:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO AnalysisRuns (
            aggregation_interval_minutes, target_metric, status, summary_json
        ) VALUES (?, ?, ?, ?)
        """,
        (
            interval_minutes,
            target_metric,
            "ready" if aggregation["summary"]["eligible_for_forecasting"] else "ineligible",
            json.dumps(aggregation, ensure_ascii=False, separators=(",", ":")),
        ),
    )
    analysis_id = int(cur.lastrowid)
    cur.executemany(
        "INSERT INTO AnalysisRunDatasets (analysis_run_id, import_id) VALUES (?, ?)",
        [(analysis_id, dataset_id) for dataset_id in dataset_ids],
    )
    conn.commit()
    conn.close()
    return analysis_id


def create_time_series_analysis(
    dataset_ids: list[int],
    interval_minutes: int = 5,
    target_metric: str = "vehicle_count",
    db_path: Path = DB_PATH,
) -> dict:
    selected_ids = _validate_selection(dataset_ids, interval_minutes, target_metric)
    aggregation = _build_series(selected_ids, interval_minutes, target_metric, db_path)
    analysis_id = _persist_analysis(
        aggregation, selected_ids, interval_minutes, target_metric, db_path
    )
    return {"analysis_run_id": analysis_id, **aggregation}


def run_multi_dataset_forecast(
    dataset_ids: list[int],
    interval_minutes: int = 5,
    target_metric: str = "vehicle_count",
    horizon: int = 6,
    db_path: Path = DB_PATH,
) -> dict:
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 288:
        raise ValueError("Forecast horizon phải nằm trong khoảng 1–288.")
    selected_ids = _validate_selection(dataset_ids, interval_minutes, target_metric)
    aggregation = _build_series(selected_ids, interval_minutes, target_metric, db_path)
    analysis_id = _persist_analysis(
        aggregation, selected_ids, interval_minutes, target_metric, db_path
    )
    summary = aggregation["summary"]
    series = aggregation["series"]
    if summary["missing_timestamp_count"]:
        raise ValueError(
            f"Có {summary['missing_timestamp_count']} khoảng thời gian bị thiếu. "
            "Hệ thống không tự điền dữ liệu giả; hãy chọn các Dataset có chuỗi thời gian liên tục."
        )
    if len(series) < 12:
        raise ValueError("Cần ít nhất 12 khoảng thời gian liên tục để huấn luyện và đánh giá.")

    values = np.asarray([point[target_metric] for point in series], dtype=float)
    holdout_count = max(2, int(math.ceil(len(values) * 0.2)))
    train_count = len(values) - holdout_count
    if train_count < 10:
        raise ValueError("Dữ liệu không đủ dài để tạo tập train và time-based holdout.")
    train_values = values[:train_count]
    actual_holdout = values[train_count:]

    _, arima_holdout, arima_lower, arima_upper, arima_parameters = _fit_predict_arima(
        train_values, holdout_count
    )
    _, prophet_holdout, prophet_lower, prophet_upper, prophet_parameters = _fit_predict_prophet(
        train_values, holdout_count
    )
    arima_metrics = _calc_metrics(actual_holdout, arima_holdout)
    prophet_metrics = _calc_metrics(actual_holdout, prophet_holdout)
    _, arima_future, arima_future_lower, arima_future_upper, _ = _fit_predict_arima(
        values, horizon
    )
    _, prophet_future, prophet_future_lower, prophet_future_upper, _ = _fit_predict_prophet(
        values, horizon
    )

    start = datetime.fromisoformat(series[0]["timestamp"])
    last_timestamp = datetime.fromisoformat(series[-1]["timestamp"])
    holdout_points = series[train_count:]
    future_timestamps = [
        (last_timestamp + timedelta(minutes=interval_minutes * step)).isoformat(sep=" ")
        for step in range(1, horizon + 1)
    ]
    parameters = {
        "ARIMA": arima_parameters,
        "Prophet": prophet_parameters,
        "validation": "time-based holdout (last 20%; same observations for both models)",
    }
    metrics = {"ARIMA": arima_metrics, "Prophet": prophet_metrics}

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ForecastRuns (
            analysis_run_id, training_start, training_end, forecast_horizon,
            aggregation_interval_minutes, target_metric, model_parameters_json,
            evaluation_metrics_json, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed')
        """,
        (
            analysis_id,
            start.isoformat(sep=" "),
            last_timestamp.isoformat(sep=" "),
            horizon,
            interval_minutes,
            target_metric,
            json.dumps(parameters, ensure_ascii=False),
            json.dumps(metrics, ensure_ascii=False),
        ),
    )
    forecast_id = int(cur.lastrowid)
    cur.executemany(
        "INSERT INTO ForecastRunDatasets (forecast_run_id, import_id) VALUES (?, ?)",
        [(forecast_id, dataset_id) for dataset_id in selected_ids],
    )
    results = []
    for index, point in enumerate(holdout_points):
        results.extend([
            (
                forecast_id, "ARIMA", "holdout", point["timestamp"],
                float(actual_holdout[index]), float(arima_holdout[index]),
                float(arima_lower[index]), float(arima_upper[index]),
            ),
            (
                forecast_id, "Prophet", "holdout", point["timestamp"],
                float(actual_holdout[index]), float(prophet_holdout[index]),
                float(prophet_lower[index]), float(prophet_upper[index]),
            ),
        ])
    for index, timestamp in enumerate(future_timestamps):
        results.extend([
            (
                forecast_id, "ARIMA", "future", timestamp, None,
                float(arima_future[index]), float(arima_future_lower[index]),
                float(arima_future_upper[index]),
            ),
            (
                forecast_id, "Prophet", "future", timestamp, None,
                float(prophet_future[index]), float(prophet_future_lower[index]),
                float(prophet_future_upper[index]),
            ),
        ])
    cur.executemany(
        """
        INSERT INTO ForecastResults (
            forecast_run_id, model_name, result_type, timestamp, actual_value,
            predicted_value, lower_bound, upper_bound
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        results,
    )
    conn.commit()
    conn.close()
    return {
        "forecast_run_id": forecast_id,
        "analysis_run_id": analysis_id,
        "dataset_count": len(selected_ids),
        "series_count": len(series),
        "summary": summary,
        "metrics": metrics,
        "results": results,
    }


def get_forecast_history(db_path: Path = DB_PATH, limit: int = 50) -> list[dict]:
    init_db(db_path)
    limit = min(100, max(1, int(limit)))
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT f.forecast_run_id, f.created_at, f.target_metric, f.training_start,
               f.training_end, f.forecast_horizon, f.evaluation_metrics_json,
               COUNT(fd.import_id) AS dataset_count
        FROM ForecastRuns f
        JOIN ForecastRunDatasets fd ON fd.forecast_run_id = f.forecast_run_id
        GROUP BY f.forecast_run_id
        ORDER BY f.forecast_run_id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    forecasts = []
    for row in rows:
        metrics = json.loads(row[6])
        forecasts.append({
            "forecast_run_id": row[0],
            "created_at": row[1],
            "target_metric": row[2],
            "training_start": row[3],
            "training_end": row[4],
            "forecast_horizon": row[5],
            "arima_mae": metrics["ARIMA"]["mae"],
            "prophet_mae": metrics["Prophet"]["mae"],
            "arima_rmse": metrics["ARIMA"]["rmse"],
            "prophet_rmse": metrics["Prophet"]["rmse"],
            "dataset_count": row[7],
        })
    return forecasts


def get_forecast_details(forecast_run_id: int, db_path: Path = DB_PATH) -> dict | None:
    init_db(db_path)
    conn = get_connection(db_path)
    run = conn.execute(
        """
        SELECT forecast_run_id, analysis_run_id, training_start, training_end,
               forecast_horizon, aggregation_interval_minutes, target_metric,
               model_parameters_json, evaluation_metrics_json, created_at
        FROM ForecastRuns
        WHERE forecast_run_id = ?
        """,
        (forecast_run_id,),
    ).fetchone()
    if run is None:
        conn.close()
        return None
    dataset_ids = [
        row[0] for row in conn.execute(
            "SELECT import_id FROM ForecastRunDatasets WHERE forecast_run_id = ? ORDER BY import_id",
            (forecast_run_id,),
        )
    ]
    results = conn.execute(
        """
        SELECT model_name, result_type, timestamp, actual_value, predicted_value,
               lower_bound, upper_bound
        FROM ForecastResults
        WHERE forecast_run_id = ?
        ORDER BY CASE result_type WHEN 'holdout' THEN 0 ELSE 1 END, timestamp, model_name
        """,
        (forecast_run_id,),
    ).fetchall()
    conn.close()
    return {
        "forecast_run_id": run[0],
        "analysis_run_id": run[1],
        "training_start": run[2],
        "training_end": run[3],
        "forecast_horizon": run[4],
        "interval_minutes": run[5],
        "target_metric": run[6],
        "model_parameters": json.loads(run[7]),
        "metrics": json.loads(run[8]),
        "created_at": run[9],
        "dataset_ids": dataset_ids,
        "results": [
            {
                "model_name": row[0],
                "result_type": row[1],
                "timestamp": row[2],
                "actual_value": row[3],
                "predicted_value": row[4],
                "lower_bound": row[5],
                "upper_bound": row[6],
                "forecast_error": (
                    float(row[4]) - float(row[3]) if row[3] is not None else None
                ),
            }
            for row in results
        ],
    }


def get_analysis_history(db_path: Path = DB_PATH, limit: int = 50) -> list[dict]:
    init_db(db_path)
    limit = min(100, max(1, int(limit)))
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT a.analysis_run_id, a.aggregation_interval_minutes, a.target_metric,
               a.status, a.summary_json, a.created_at,
               GROUP_CONCAT(ad.import_id) AS dataset_ids
        FROM AnalysisRuns a
        JOIN AnalysisRunDatasets ad ON ad.analysis_run_id = a.analysis_run_id
        GROUP BY a.analysis_run_id
        ORDER BY a.analysis_run_id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    history = []
    for row in rows:
        summary = json.loads(row[4])["summary"]
        history.append({
            "analysis_run_id": row[0],
            "interval_minutes": row[1],
            "target_metric": row[2],
            "status": row[3],
            "created_at": row[5],
            "dataset_ids": [int(value) for value in row[6].split(",")],
            "series_count": summary["series_count"],
            "missing_timestamp_count": summary["missing_timestamp_count"],
            "training_start": summary["training_start"],
            "training_end": summary["training_end"],
        })
    return history
