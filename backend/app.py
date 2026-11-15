
import argparse
import base64
import hashlib
import json
import logging
import mimetypes
import os
import subprocess
import sys
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
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

from db_manager import (
    DB_PATH,
    clear_all_database_data,
    delete_dataset_permanently,
    find_dataset_by_checksum,
    get_connection,
    get_dataset_filter_options,
    get_table_counts_df,
    init_db,
    list_datasets,
)
_DEFAULT_DB_PATH = DB_PATH
from module1_dataset_management import (
    DuplicateDatasetError,
    MAX_FILE_SIZE_KB,
    process_and_ingest_uploaded_file,
)
from module2_pattern_analysis import get_module2_dashboard_data
from module3_forecasting import get_module3_forecast_data
from module4_visualization_dashboard import get_module4_visualization_data
from module5_experiment_management import get_module5_experiment_data, run_custom_experiment
from module6_reporting import get_module6_reporting_data, log_and_generate_report
from multi_dataset_analysis import (
    create_time_series_analysis,
    get_analysis_history,
    get_forecast_details,
    get_forecast_history,
    run_multi_dataset_forecast,
)


def collect_full_state_bundle(
    db_path: Path = DB_PATH,
    dataset_id: int | None = None,
) -> dict:
    """Collect data for all six modules without mutating existing records."""
    m2_all = get_module2_dashboard_data(
        "ALL", "ALL", db_path=db_path, dataset_id=dataset_id
    )
    if not m2_all.get("has_data"):
        return {
            "has_data": False,
            "db_tables": get_table_counts_df(db_path=db_path).to_dict(orient="records"),
        }

    zones = m2_all["filters"]["zones"]
    timeframes = m2_all["filters"]["timeframes"]

    # Tiền tính toán mọi tổ hợp lọc (zone_id × timeframe_id) để chuyển nút lọc trên Web cực nhạy (< 1ms)
    m2_combinations = {"ALL__ALL": m2_all}
    for z in zones:
        zid = str(z["zone_id"])
        m2_combinations[f"{zid}__ALL"] = get_module2_dashboard_data(
            zid, "ALL", db_path=db_path, dataset_id=dataset_id
        )
        for tf in timeframes:
            tfid = str(tf["timeframe_id"])
            m2_combinations[f"{zid}__{tfid}"] = get_module2_dashboard_data(
                zid, tfid, db_path=db_path, dataset_id=dataset_id
            )
    for tf in timeframes:
        tfid = str(tf["timeframe_id"])
        m2_combinations[f"ALL__{tfid}"] = get_module2_dashboard_data(
            "ALL", tfid, db_path=db_path, dataset_id=dataset_id
        )

    m3_by_zone = {}
    for z in zones:
        zid = int(z["zone_id"])
        m3_by_zone[str(zid)] = get_module3_forecast_data(
            zid,
            day_horizon="DAY_0",
            timeframe_id=None,
            db_path=db_path,
            dataset_id=int(m2_all["filters"]["import_info"]["import_id"]),
        )

    selected_ids = [int(m2_all["filters"]["import_info"]["import_id"])]
    m4_data = get_module4_visualization_data(db_path=db_path, dataset_ids=selected_ids)
    m5_data = get_module5_experiment_data(db_path=db_path, dataset_ids=selected_ids)
    m6_data = get_module6_reporting_data(db_path=db_path, dataset_ids=selected_ids)
    db_tables = get_table_counts_df(db_path=db_path).to_dict(orient="records")

    conn = get_connection(db_path)
    preview_df = pd.read_sql(
        f"""
        SELECT t.vehicle_id, t.vehicle_type, t.recorded_time_str, z.zone_name,
               t.x_coord_m, t.y_coord_m, t.speed_kmh, t.accel_ms2, t.lane_no
        FROM CleanedTrajectories t
        JOIN DynamicZones z ON t.zone_id = z.zone_id
        WHERE t.import_id IN ({','.join('?' for _ in selected_ids)})
        ORDER BY t.trajectory_id ASC
        LIMIT 8
        """,
        conn,
        params=selected_ids,
    )
    conn.close()

    return {
        "has_data": True,
        "selected_dataset_ids": selected_ids,
        "selected_dataset_count": len(selected_ids),
        "import_info": m2_all["filters"]["import_info"],
        "preview_rows": preview_df.to_dict(orient="records"),
        "zones": zones,
        "timeframes": timeframes,
        "m2_combinations": m2_combinations,
        "m3_by_zone": m3_by_zone,
        "m4_data": m4_data,
        "m5_data": m5_data,
        "m6_data": m6_data,
        "db_tables": db_tables,
    }


def build_precomputed_datasets_cache() -> dict:
    """Load current database state without generating or deleting persisted data."""
    init_db(DB_PATH)
    return {"DEFAULT_BUNDLE": collect_full_state_bundle(DB_PATH)}


FRONTEND_DIR = BASE_DIR / "frontend"
STORAGE_ROOT = BASE_DIR / "storage" / "datasets"


def generate_standalone_web_html(presets: dict) -> Path:
    """Write generated preset data to the separate frontend assets."""
    presets_path = FRONTEND_DIR / "js" / "presets.js"
    presets_json = json.dumps(presets, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    presets_path.write_text(f"window.PRESET_BUNDLES = {presets_json};\n", encoding="utf-8")
    return FRONTEND_DIR / "index.html"


class WebAppHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler xử lý Kéo thả file (.xlsx / .csv tối đa 3 GB), Nút Xóa DB và API 6 Module."""

    def _receive_legacy_json_upload(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 16 * 1024 * 1024:
            self._send_json({"error": "Legacy JSON upload chỉ hỗ trợ request tối đa 16 MB."}, 413)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            file_name = str(payload["file_name"])
            if payload.get("chunk_text"):
                file_bytes = str(payload["chunk_text"]).encode("utf-8")
            elif payload.get("file_b64"):
                file_bytes = base64.b64decode(payload["file_b64"], validate=True)
            else:
                raise ValueError("Request upload không có chunk_text hoặc file_b64.")
            result = process_and_ingest_uploaded_file(
                file_name=file_name,
                file_bytes=file_bytes,
                db_path=DB_PATH,
                override_size_kb=float(payload.get("file_size_kb", 0)) or None,
                storage_root=STORAGE_ROOT,
            )
        except DuplicateDatasetError as exc:
            self._send_json({"error": str(exc), "duplicate": exc.dataset}, 409)
            return
        except (KeyError, ValueError, UnicodeDecodeError) as exc:
            self._send_json({"error": str(exc)}, 400)
            return
        self._send_json(
            {"result": result, "bundle": collect_full_state_bundle(DB_PATH)}
        )

    def _receive_dataset_upload(self, parsed) -> None:
        query = parse_qs(parsed.query)
        raw_name = query.get("filename", [""])[0]
        file_name = Path(raw_name.replace("\\", "/")).name
        if not file_name:
            self._send_json({"error": "Thiếu tên file upload."}, 400)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"error": "Content-Length không hợp lệ."}, 400)
            return
        max_bytes = int(MAX_FILE_SIZE_KB * 1024)
        if content_length <= 0 or content_length > max_bytes:
            self._send_json({"error": "File rỗng hoặc vượt quá giới hạn 3 GB."}, 413)
            return

        staging_root = STORAGE_ROOT.parent / ".staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        staged_path = staging_root / f"{uuid.uuid4()}.upload"
        digest = hashlib.sha256()
        remaining = content_length
        try:
            with staged_path.open("wb") as target:
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ConnectionError("Upload bị ngắt trước khi nhận đủ dữ liệu.")
                    target.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)

            checksum = digest.hexdigest()
            duplicate = find_dataset_by_checksum(checksum, DB_PATH)
            allow_duplicate = query.get("allow_duplicate", ["0"])[0] == "1"
            if duplicate and not allow_duplicate:
                staged_path.unlink(missing_ok=True)
                self._send_json(
                    {
                        "error": "Nội dung file đã tồn tại; không có dữ liệu nào bị ghi đè.",
                        "duplicate": duplicate,
                    },
                    409,
                )
                return

            manual_metadata = {
                key: query.get(key, [""])[0]
                for key in ("capture_date", "drone_id", "start_time", "end_time")
            }
            manual_metadata = {key: value for key, value in manual_metadata.items() if value}
            result = process_and_ingest_uploaded_file(
                file_name=file_name,
                file_path=staged_path,
                db_path=DB_PATH,
                override_size_kb=content_length / 1024.0,
                dataset_uuid=str(uuid.uuid4()),
                checksum_sha256=checksum,
                allow_duplicate=allow_duplicate,
                storage_root=STORAGE_ROOT,
                manual_metadata=manual_metadata,
            )
            bundle = collect_full_state_bundle(DB_PATH)
            if DB_PATH == _DEFAULT_DB_PATH:
                generate_standalone_web_html({"DEFAULT_BUNDLE": bundle})
            self._send_json(
                {
                    "result": result,
                    "bundle": bundle,
                    "datasets": list_datasets(DB_PATH, page=1, page_size=25),
                }
            )
        except DuplicateDatasetError as exc:
            staged_path.unlink(missing_ok=True)
            self._send_json({"error": str(exc), "duplicate": exc.dataset}, 409)
        except (ValueError, FileNotFoundError) as exc:
            staged_path.unlink(missing_ok=True)
            logging.warning("Dataset upload rejected for %s: %s", file_name, exc)
            self._send_json({"error": str(exc)}, 400)
        except Exception as exc:
            staged_path.unlink(missing_ok=True)
            logging.exception("Dataset upload failed for %s", file_name)
            self._send_json({"error": f"Không thể xử lý dataset: {exc}"}, 500)

    def _send_json(self, obj: object, code: int = 200) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, file_path: Path, content_type: str | None = None) -> None:
        raw = file_path.read_bytes()
        guessed_type = content_type or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if guessed_type.startswith(("text/", "application/javascript")) and "charset=" not in guessed_type:
            guessed_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", guessed_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html", "/Web_App_4_Module_UAV.html"):
            self._send_file(FRONTEND_DIR / "index.html", "text/html; charset=utf-8")
        elif parsed.path.startswith("/static/"):
            frontend_root = FRONTEND_DIR.resolve()
            asset_path = (frontend_root / unquote(parsed.path[len("/static/"):])).resolve()
            try:
                asset_path.relative_to(frontend_root)
            except ValueError:
                self._send_json({"error": "Not found"}, 404)
                return
            if not asset_path.is_file():
                self._send_json({"error": "Not found"}, 404)
                return
            self._send_file(asset_path)
        elif parsed.path == "/api/state":
            query = parse_qs(parsed.query)
            raw_dataset_id = query.get("dataset_id", [None])[0]
            try:
                dataset_id = int(raw_dataset_id) if raw_dataset_id is not None else None
                self._send_json(collect_full_state_bundle(DB_PATH, dataset_id))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 422)
        elif parsed.path == "/api/datasets":
            query = parse_qs(parsed.query)
            try:
                data = list_datasets(
                    DB_PATH,
                    page=int(query.get("page", ["1"])[0]),
                    page_size=int(query.get("page_size", ["25"])[0]),
                    filename=query.get("filename", [""])[0],
                    capture_date=query.get("capture_date", [""])[0],
                    drone_id=query.get("drone_id", [""])[0],
                    start_time=query.get("start_time", [""])[0],
                    end_time=query.get("end_time", [""])[0],
                    processing_status=query.get("processing_status", [""])[0],
                    file_extension=query.get("file_extension", [""])[0],
                )
            except ValueError:
                self._send_json({"error": "Tham số phân trang không hợp lệ."}, 400)
                return
            self._send_json(data)
        elif parsed.path == "/api/dataset-options":
            self._send_json(get_dataset_filter_options(DB_PATH))
        elif parsed.path == "/api/forecast/history":
            self._send_json({"forecasts": get_forecast_history(DB_PATH)})
        elif parsed.path == "/api/analysis/history":
            self._send_json({"analyses": get_analysis_history(DB_PATH)})
        elif parsed.path.startswith("/api/forecast/history/"):
            try:
                forecast_id = int(parsed.path.rsplit("/", 1)[1])
            except ValueError:
                self._send_json({"error": "Forecast ID không hợp lệ."}, 400)
                return
            details = get_forecast_details(forecast_id, DB_PATH)
            if details is None:
                self._send_json({"error": "Không tìm thấy Forecast Run."}, 404)
                return
            self._send_json(details)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/m1/upload":
            content_type = self.headers.get("Content-Type", "").lower()
            if content_type.startswith("application/json"):
                self._receive_legacy_json_upload()
                return
            self._receive_dataset_upload(parsed)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body_bytes = self.rfile.read(length) if length > 0 else b"{}"

        if parsed.path == "/api/analysis/time-series":
            payload = json.loads(body_bytes.decode("utf-8"))
            try:
                result = create_time_series_analysis(
                    dataset_ids=payload.get("dataset_ids", []),
                    interval_minutes=int(payload.get("interval_minutes", 5)),
                    target_metric=str(payload.get("target_metric", "vehicle_count")),
                    db_path=DB_PATH,
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 422)
                return
            self._send_json(result)
        elif parsed.path == "/api/forecast/multi":
            payload = json.loads(body_bytes.decode("utf-8"))
            try:
                result = run_multi_dataset_forecast(
                    dataset_ids=payload.get("dataset_ids", []),
                    interval_minutes=int(payload.get("interval_minutes", 5)),
                    target_metric=str(payload.get("target_metric", "vehicle_count")),
                    horizon=int(payload.get("horizon", 6)),
                    db_path=DB_PATH,
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 422)
                return
            self._send_json(result)
        elif parsed.path == "/api/m5/run":
            payload = json.loads(body_bytes.decode("utf-8"))
            try:
                dataset_ids = payload.get("dataset_ids") or []
                if len(dataset_ids) > 1:
                    raise ValueError("Chỉ hỗ trợ một Dataset cho mỗi lần chạy thực nghiệm.")
                run_custom_experiment(
                    zone_id=int(payload.get("zone_id", 1)),
                    temporal_interval_sec=int(payload.get("temporal_interval_sec", 60)),
                    train_ratio=float(payload.get("train_ratio", 0.75)),
                    arima_order_str=str(payload.get("arima_order_str", "ARIMA(1,1,1)")),
                    prophet_fourier_k=int(payload.get("prophet_fourier_k", 3)),
                    prophet_changepoint_scale=float(payload.get("prophet_changepoint_scale", 0.15)),
                    random_seed=int(payload.get("random_seed", 42)),
                    dataset_version=str(payload.get("dataset_version", "v2.0-Custom")),
                    db_path=DB_PATH,
                    dataset_ids=dataset_ids or None,
                )
                self._send_json({
                    "bundle": collect_full_state_bundle(
                        DB_PATH, dataset_id=int(dataset_ids[0]) if dataset_ids else None
                    )
                })
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 422)
        elif parsed.path == "/api/m6/export":
            payload = json.loads(body_bytes.decode("utf-8"))
            try:
                dataset_ids = payload.get("dataset_ids") or []
                if len(dataset_ids) > 1:
                    raise ValueError("Chỉ hỗ trợ một Dataset cho mỗi lần xuất báo cáo.")
                log_and_generate_report(
                    report_type=str(payload.get("report_type", "Comprehensive_Full")),
                    export_format=str(payload.get("export_format", "PDF")),
                    zone_scope=str(payload.get("zone_scope", "Tất cả Khu vực động")),
                    horizon_scope=str(payload.get("horizon_scope", "Ngày gốc + Dự báo 2 ngày sau đó (+48h)")),
                    db_path=DB_PATH,
                    dataset_ids=dataset_ids or None,
                )
                self._send_json({
                    "bundle": collect_full_state_bundle(
                        DB_PATH, dataset_id=int(dataset_ids[0]) if dataset_ids else None
                    )
                })
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 422)
        elif parsed.path == "/api/m1/delete":
            res = clear_all_database_data(DB_PATH, STORAGE_ROOT)
            bundle = collect_full_state_bundle(DB_PATH)
            if DB_PATH == _DEFAULT_DB_PATH:
                generate_standalone_web_html({"DEFAULT_BUNDLE": bundle})
            self._send_json({
                **res,
                "bundle": bundle,
                "datasets": list_datasets(DB_PATH, page=1, page_size=25),
            })
        elif parsed.path in ("/api/datasets/delete", "/api/datasets/permanent-delete"):
            try:
                payload = json.loads(body_bytes.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Dữ liệu yêu cầu không hợp lệ.")
                dataset_id = int(payload.get("dataset_id", 0))
                result = delete_dataset_permanently(dataset_id, DB_PATH, STORAGE_ROOT)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                self._send_json({"error": str(exc) or "Dataset ID không hợp lệ."}, 400)
                return
            except OSError as exc:
                logging.exception("Could not remove original file for dataset deletion")
                self._send_json(
                    {"error": f"Không thể xóa file gốc của Dataset: {exc}"},
                    500,
                )
                return
            if result is None:
                self._send_json({"error": "Dataset không tồn tại."}, 404)
                return
            bundle = collect_full_state_bundle(DB_PATH)
            if DB_PATH == _DEFAULT_DB_PATH:
                generate_standalone_web_html({"DEFAULT_BUNDLE": bundle})
            self._send_json({
                **result,
                "bundle": bundle,
                "datasets": list_datasets(DB_PATH, page=1, page_size=25),
            })
        else:
            self._send_json({"error": "Invalid endpoint"}, 404)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy Ứng dụng Web 6 Module Phân tích & Dự báo Giao thông UAV")
    parser.add_argument("--serve", action="store_true", help="Khởi chạy HTTP Web Server tại http://localhost:8080")
    parser.add_argument("--port", type=int, default=8080, help="Cổng chạy Web Server (mặc định: 8080)")
    args = parser.parse_args()

    print("=" * 95)
    print("🚀 ĐANG KHỞI TẠO HỆ THỐNG CSDL ĐỘNG 9 BẢNG & XUẤT GIAO DIỆN WEB 6 MODULE...")
    print("=" * 95)
    presets = build_precomputed_datasets_cache()
    html_path = generate_standalone_web_html(presets)

    print(f"✅ Đã nạp Database 14 bảng (9 bảng cốt lõi + 5 bảng lịch sử) tại: {DB_PATH}")
    print(f"✅ Đã xuất Giao diện Web tại   : {html_path}")
    print("\nBảng kiểm tra số dòng hiện tại trong 14 bảng của UrbanTrafficDynamicDB:")
    print(get_table_counts_df(DB_PATH).to_string(index=False))

    if args.serve:
        url = f"http://localhost:{args.port}"
        print(f"\n🌐 Web Server 6 Module đang chạy tại: {url}")
        webbrowser.open(url)
        server = HTTPServer(("0.0.0.0", args.port), WebAppHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nĐã dừng Web Server.")


if __name__ == "__main__":
    main()
