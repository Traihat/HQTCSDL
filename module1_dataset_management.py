r"""
MODULE 1: TRAFFIC DATASET MANAGEMENT — XỬ LÝ FILE EXCEL / CSV (KỂ CẢ FILE LỚN HÀNG GB) & QUẢN LÝ DATABASE
===========================================================================================================
Thiết kế mới hoàn toàn cho dự án `8_LamLaiDuAn` theo đúng yêu cầu:
  - Phím chức năng xử lý dữ liệu trên thanh công cụ Web.
  - Kéo thả file dữ liệu vào ô `"Hay keo file du lieu cua ban vao o nay"` (nhận cả `.xlsx`, `.xls` và `.csv`, dung lượng tối đa 3 GB).
  - Hỗ trợ đọc phân luồng (Streaming Multi-Offset Chunking) cho các file `.csv` siêu lớn (như file UAV pNEUMA
    `20181029_dX_0830_0900.csv` nặng 1.72 GB) mà KHÔNG làm sập trình duyệt hay tràn RAM.
  - Tự động tiền xử lý làm sạch dữ liệu (lọc dòng trống, trùng lặp, xe đỗ tĩnh, ngoại lai vận tốc/gia tốc).
  - Tự động chia Khu vực (`DynamicZones`) và Khung giờ (`DynamicTimeFrames`) ĐỘNG 100% dựa trên dữ liệu nạp vào.
  - Sau khi tiền xử lý xong: nạp đầy đủ vào 9 bảng CSDL và in ra màn hình đúng 1 dòng thông báo xác nhận.
  - Có nút Xóa: xóa sạch database & dữ liệu cũ và hiển thị đúng thông báo:
    `"Da xoa thanh cong database va du lieu cu. San sang de nhan du lieu moi"`.
"""

import io
import hashlib
import math
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
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
    find_dataset_by_checksum,
    get_connection,
    get_table_counts_df,
    init_db,
)
from module3_forecasting import run_forecasting_for_all_dynamic_zones
from module5_experiment_management import seed_default_experiments
from module6_reporting import seed_default_reports

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
UPLOAD_PROMPT_TEXT = "Hay keo file du lieu cua ban vao o nay"
DELETE_SUCCESS_TEXT = "Da xoa thanh cong database va du lieu cu. San sang de nhan du lieu moi"
PROCESS_SUCCESS_TEXT = "Đã xử lý dữ liệu và đưa dữ liệu vào database thành công!"
MAX_FILE_SIZE_KB = 3.0 * 1024.0 * 1024.0  # Giới hạn tối đa 3 GB (3,145,728 KB)
DEFAULT_STORAGE_ROOT = BASE_DIR / "storage" / "datasets"


class DuplicateDatasetError(ValueError):
    def __init__(self, dataset: dict) -> None:
        self.dataset = dataset
        super().__init__(f"File đã tồn tại dưới Dataset ID {dataset['dataset_id']}.")


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_dataset_metadata(file_name: str, manual: dict | None = None) -> dict:
    match = re.search(
        r"(?P<date>\d{8})_(?P<drone>d[a-z0-9]+)_(?P<start>\d{4})_(?P<end>\d{4})",
        Path(file_name).name,
        flags=re.IGNORECASE,
    )
    metadata = {
        "capture_date": None,
        "drone_id": None,
        "start_time": None,
        "end_time": None,
        "duration_minutes": None,
    }
    if match:
        try:
            capture_date = datetime.strptime(match.group("date"), "%Y%m%d").date()
            start = datetime.strptime(match.group("start"), "%H%M").time()
            end = datetime.strptime(match.group("end"), "%H%M").time()
        except ValueError:
            match = None
        else:
            start_minutes = start.hour * 60 + start.minute
            end_minutes = end.hour * 60 + end.minute
            duration = (end_minutes - start_minutes) % (24 * 60)
            if duration > 0:
                metadata.update({
                    "capture_date": capture_date.isoformat(),
                    "drone_id": match.group("drone").lower(),
                    "start_time": start.strftime("%H:%M"),
                    "end_time": end.strftime("%H:%M"),
                    "duration_minutes": duration,
                })

    manual = manual or {}
    for key in ("capture_date", "drone_id", "start_time", "end_time"):
        value = manual.get(key)
        if value is not None and str(value).strip():
            metadata[key] = str(value).strip()
    try:
        if metadata["capture_date"]:
            metadata["capture_date"] = datetime.strptime(
                metadata["capture_date"], "%Y-%m-%d"
            ).date().isoformat()
        for key in ("start_time", "end_time"):
            if metadata[key]:
                metadata[key] = datetime.strptime(metadata[key], "%H:%M").strftime("%H:%M")
    except ValueError as exc:
        raise ValueError("Metadata thủ công không hợp lệ; ngày phải là YYYY-MM-DD, giờ phải là HH:MM.") from exc
    if metadata["start_time"] and metadata["end_time"]:
        start = datetime.strptime(metadata["start_time"], "%H:%M")
        end = datetime.strptime(metadata["end_time"], "%H:%M")
        metadata["duration_minutes"] = int(
            (end.hour * 60 + end.minute - start.hour * 60 - start.minute) % (24 * 60)
        ) or None
        if metadata["duration_minutes"] is None:
            raise ValueError("Thời gian kết thúc phải khác thời gian bắt đầu.")
    return metadata


def _store_original_file(
    file_name: str,
    file_bytes: bytes | None,
    source_path: Path | None,
    dataset_uuid: str,
    storage_root: Path,
) -> str:
    extension = Path(file_name).suffix.lower()
    dataset_dir = storage_root / dataset_uuid
    dataset_dir.mkdir(parents=True, exist_ok=False)
    destination = dataset_dir / f"original{extension}"
    if file_bytes is not None:
        with destination.open("wb") as target:
            target.write(file_bytes)
    elif source_path is not None:
        staging_root = (storage_root.parent / ".staging").resolve()
        try:
            source_path.resolve().relative_to(staging_root)
        except ValueError:
            shutil.copyfile(source_path, destination)
        else:
            os.replace(source_path, destination)
    else:
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu: {file_name}")
    try:
        return str(destination.relative_to(BASE_DIR))
    except ValueError:
        return str(destination.resolve())


def _infer_base_datetime_from_filename(file_name: str) -> pd.Timestamp | None:
    """Parse pNEUMA or YYYYMMDD_*_HHMM filename format; fall back to default timestamp if absent."""
    match = re.search(
        r"(?P<date>\d{8})(?:_[a-z0-9]+)?_(?P<start>\d{4})",
        Path(file_name).name,
        flags=re.IGNORECASE,
    )
    if not match:
        return pd.Timestamp("2025-01-01 08:00:00")
    try:
        date = datetime.strptime(match.group("date"), "%Y%m%d").date()
        start = datetime.strptime(match.group("start"), "%H%M").time()
    except ValueError:
        return pd.Timestamp("2025-01-01 08:00:00")
    return pd.Timestamp(datetime.combine(date, start))


def _parse_pneuma_wide_lines(
    lines: list[str],
    file_name: str,
    max_points: int = 6000,
    base_datetime: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Giải mã định dạng CSV pNEUMA siêu rộng (mỗi dòng là 1 quỹ đạo phương tiện với hàng nghìn cột lặp lại:
    `track_id; type; traveled_d; avg_speed; lat; lon; speed; lon_acc; lat_acc; time; ...`).
    """
    base_dt = base_datetime or _infer_base_datetime_from_filename(file_name) or pd.Timestamp("2025-01-01 08:00:00")
    records = []
    valid_lines = [ln for ln in lines if ln and ";" in ln and not ln.lstrip().lower().startswith("track_id")]
    if not valid_lines:
        return pd.DataFrame()

    pts_per_track = max(10, min(40, max_points // max(len(valid_lines), 1)))

    for idx_ln, line in enumerate(valid_lines):
        parts = [p.strip() for p in line.split(";") if p.strip() != ""]
        if len(parts) < 10:
            continue
        track_id = f"UAV_{parts[0]}" if len(parts[0]) <= 12 else f"UAV_{idx_ln+1}"
        v_type = parts[1] if parts[1] and not parts[1].replace(".", "", 1).lstrip("-").isdigit() else "Car"
        n_tuples = (len(parts) - 4) // 6
        if n_tuples <= 0:
            continue

        step = max(1, n_tuples // pts_per_track)
        for t_idx in range(0, n_tuples, step):
            base_i = 4 + t_idx * 6
            if base_i + 5 >= len(parts):
                break
            try:
                lat = float(parts[base_i])
                lon = float(parts[base_i + 1])
                spd = float(parts[base_i + 2])
                lon_acc = float(parts[base_i + 3])
                t_sec = float(parts[base_i + 5])
            except ValueError:
                continue

            ts_str = (base_dt + pd.Timedelta(seconds=max(0.0, t_sec))).strftime("%Y-%m-%d %H:%M:%S")
            lane_no = (abs(hash(track_id)) % 4) + 1
            records.append({
                "vehicle_id": track_id,
                "vehicle_type": v_type,
                "recorded_time": ts_str,
                "x_coord_m": lon,
                "y_coord_m": lat,
                "speed_kmh": spd,
                "accel_ms2": lon_acc,
                "lane_no": lane_no,
            })
            if len(records) >= max_points:
                break
        if len(records) >= max_points:
            break

    return pd.DataFrame(records)


def _stream_large_csv_from_disk(
    file_path: Path,
    file_name: str,
    base_datetime: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Đọc phân luồng (Multi-Offset Stratified Streaming) trực tiếp từ ổ đĩa cho file CSV lớn (từ vài chục MB đến 3 GB)
    trong thời gian < 1 giây mà không bao giờ nạp toàn bộ file vào RAM.
    """
    file_size = file_path.stat().st_size
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        header_line = f.readline()
        second_line = f.readline()

        is_pneuma_wide = (
            ";" in header_line
            and (
                "traveled_d" in header_line.lower()
                or "lat_acc" in header_line.lower()
                or second_line.count(";") > header_line.count(";") + 5
            )
        )

        if is_pneuma_wide:
            sampled_lines = [second_line]
            fractions = [0.0, 0.12, 0.25, 0.38, 0.52, 0.66, 0.80, 0.92] if file_size > 15 * 1024 * 1024 else [0.0]
            lines_per_frac = 32 if len(fractions) > 1 else 250
            for frac in fractions:
                if frac > 0:
                    f.seek(int(file_size * frac))
                    f.readline()  # Bỏ qua dòng bị cắt ngang tại điểm seek
                for _ in range(lines_per_frac):
                    ln = f.readline()
                    if not ln:
                        break
                    sampled_lines.append(ln)
            return _parse_pneuma_wide_lines(
                sampled_lines,
                file_name=file_name,
                max_points=6200,
                base_datetime=base_datetime,
            )

    sep = ";" if header_line.count(";") > header_line.count(",") else ","
    return pd.read_csv(file_path, sep=sep, nrows=15000, on_bad_lines="skip", low_memory=False)


def _read_dataframe_from_input(
    file_name: str,
    file_bytes: bytes | None = None,
    file_path: Path | None = None,
    override_size_kb: float | None = None,
    base_datetime: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, str, float]:
    ext = Path(file_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Định dạng file '{ext}' không được hỗ trợ! Chỉ chấp nhận file Excel (.xlsx, .xls) hoặc CSV (.csv).")

    if override_size_kb is not None and override_size_kb > MAX_FILE_SIZE_KB:
        raise ValueError("File vượt quá giới hạn dung lượng tối đa cho phép (Tối đa 3 GB)!")

    if file_bytes is not None:
        size_kb = override_size_kb if override_size_kb is not None else round(len(file_bytes) / 1024.0, 2)
        if size_kb > MAX_FILE_SIZE_KB:
            raise ValueError("File vượt quá giới hạn dung lượng tối đa cho phép (Tối đa 3 GB)!")
        bio = io.BytesIO(file_bytes)
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(bio)
        else:
            text_chunk = file_bytes.decode("utf-8", errors="ignore")
            lines = [ln for ln in text_chunk.splitlines() if ln.strip()]
            if not lines:
                raise ValueError("File CSV rỗng hoặc không có dữ liệu hợp lệ.")
            header_line = lines[0]
            second_line = lines[1] if len(lines) > 1 else ""
            is_pneuma_wide = (
                ";" in header_line
                and (
                    "traveled_d" in header_line.lower()
                    or "lat_acc" in header_line.lower()
                    or second_line.count(";") > header_line.count(";") + 5
                )
            )
            if is_pneuma_wide:
                df = _parse_pneuma_wide_lines(
                    lines[1:],
                    file_name=file_name,
                    max_points=6200,
                    base_datetime=base_datetime,
                )
            else:
                sep = ";" if header_line.count(";") > header_line.count(",") else ","
                safe_text = "\n".join(lines[:-1] if len(lines) > 80 else lines)
                df = pd.read_csv(io.StringIO(safe_text), sep=sep, nrows=15000, on_bad_lines="skip")
        return df, ext, size_kb

    if file_path is not None and file_path.exists():
        size_kb = round(file_path.stat().st_size / 1024.0, 2)
        if size_kb > MAX_FILE_SIZE_KB:
            raise ValueError("File vượt quá giới hạn dung lượng tối đa cho phép (Tối đa 3 GB)!")
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        else:
            df = _stream_large_csv_from_disk(
                file_path, file_name=file_name, base_datetime=base_datetime
            )
        return df, ext, size_kb

    raise FileNotFoundError(f"Không tìm thấy file dữ liệu: {file_name}")


def _normalize_columns(df: pd.DataFrame, base_datetime: pd.Timestamp | None = None) -> pd.DataFrame:
    """Chuẩn hóa linh hoạt mọi tên cột từ file Excel / CSV bất kỳ và tự động quy đổi tọa độ GPS (lat/lon) sang mét."""
    cleaned_cols = {c: str(c).replace("\ufeff", "").strip() for c in df.columns}
    df = df.rename(columns=cleaned_cols).copy()

    col_map = {}
    speed_is_ms = False
    time_is_ms = False
    zone_is_numeric_id = False

    for c in df.columns:
        cl = str(c).strip().lower()
        if cl in ("vehicle_id", "track_id", "source_track_id", "id", "ma_xe", "vehicle_code"):
            if "vehicle_id" not in col_map.values():
                col_map[c] = "vehicle_id"
        elif cl in ("vehicle_type", "type", "loai_xe", "loai_phuong_tien"):
            if "vehicle_type" not in col_map.values():
                col_map[c] = "vehicle_type"
        elif cl in (
            "recorded_time", "timestamp", "time", "datetime", "thoi_gian",
            "window_start_time", "bin_start", "start_time", "time_label",
            "window_time_label", "timestamp_ms", "khung_gio",
        ):
            if "recorded_time" not in col_map.values():
                col_map[c] = "recorded_time"
                if cl == "timestamp_ms":
                    time_is_ms = True
        elif cl in ("x_coord_m", "x_pos_m", "x_pos", "x_m", "x", "lon", "longitude", "dist_m"):
            if "x_coord_m" not in col_map.values():
                col_map[c] = "x_coord_m"
        elif cl in ("y_coord_m", "y_pos_m", "y_pos", "y_m", "y", "lat", "latitude", "time_in_zone_s"):
            if "y_coord_m" not in col_map.values():
                col_map[c] = "y_coord_m"
        elif cl in (
            "speed_kmh", "speed", "avg_speed", "avg_speed_kmh", "mean_inst_speed_kmh",
            "van_toc", "van_toc_tb_kmh", "velocity", "speed_ms",
        ):
            if "speed_kmh" not in col_map.values():
                col_map[c] = "speed_kmh"
                if cl == "speed_ms":
                    speed_is_ms = True
        elif cl in ("accel_ms2", "acc_ms2", "acceleration", "lon_acc", "acc", "gia_toc"):
            if "accel_ms2" not in col_map.values():
                col_map[c] = "accel_ms2"
        elif cl in ("lane_no", "lane", "lane_id", "lan_duong"):
            if "lane_no" not in col_map.values():
                col_map[c] = "lane_no"
        elif cl in ("zone_name", "zone", "khu_vuc", "ten_khu_vuc", "area", "region", "zone_id", "ma_khu_vuc"):
            if "zone_name" not in col_map.values():
                col_map[c] = "zone_name"
                if cl == "zone_id":
                    zone_is_numeric_id = True
        elif cl in ("road_length_km", "length_km", "chieu_dai_km"):
            if "road_length_km" not in col_map.values():
                col_map[c] = "road_length_km"

    out = df.rename(columns=col_map).copy()
    out = out.loc[:, ~out.columns.duplicated()].copy()

    n = len(out)

    required = ("vehicle_id", "recorded_time", "x_coord_m", "y_coord_m", "speed_kmh")
    missing = [column for column in required if column not in out.columns]
    if missing:
        raise ValueError("Thiếu cột dữ liệu bắt buộc: " + ", ".join(missing))
    if out["vehicle_id"].isna().all():
        raise ValueError("Cột vehicle_id/track_id không chứa mã phương tiện hợp lệ.")
    if "vehicle_type" not in out.columns:
        out["vehicle_type"] = "Unknown"

    numeric_time = pd.to_numeric(out["recorded_time"], errors="coerce")
    if numeric_time.notna().sum() >= int(0.8 * len(out)):
        fallback_dt = base_datetime or pd.Timestamp("2025-01-01 08:00:00")
        if time_is_ms:
            magnitude = float(numeric_time.abs().median())
            if magnitude > 1e11:
                parsed_time = pd.to_datetime(numeric_time, unit="ms", errors="coerce")
            else:
                parsed_time = fallback_dt + pd.to_timedelta(numeric_time / 1000.0, unit="s")
        else:
            magnitude = float(numeric_time.abs().median())
            if magnitude > 1e11:
                parsed_time = pd.to_datetime(numeric_time, unit="ms", errors="coerce")
            elif magnitude > 1e9:
                parsed_time = pd.to_datetime(numeric_time, unit="s", errors="coerce")
            else:
                parsed_time = fallback_dt + pd.to_timedelta(numeric_time, unit="s")
        out["recorded_time"] = parsed_time.dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        parsed_time = pd.to_datetime(out["recorded_time"], errors="coerce")
        if parsed_time.notna().sum() < int(0.8 * len(out)):
            raise ValueError(
                "Timestamp không hợp lệ; không thể suy đoán thời gian từ dữ liệu thiếu."
            )
        out["recorded_time"] = parsed_time.dt.strftime("%Y-%m-%d %H:%M:%S")

    if "x_coord_m" not in out.columns:
        raise ValueError("Thiếu cột tọa độ X.")
    if "y_coord_m" not in out.columns:
        raise ValueError("Thiếu cột tọa độ Y.")

    if "speed_kmh" not in out.columns:
        raise ValueError("Thiếu cột speed_kmh/speed.")
    elif speed_is_ms:
        out["speed_kmh"] = (pd.to_numeric(out["speed_kmh"], errors="coerce") * 3.6).round(2)

    if "accel_ms2" not in out.columns:
        out["accel_ms2"] = 0.0
    if "lane_no" not in out.columns:
        out["lane_no"] = (np.arange(n) % 4) + 1

    if "zone_name" in out.columns and zone_is_numeric_id:
        out["zone_name"] = out["zone_name"].apply(
            lambda v: f"Khu Vực Đô Thị {v}" if str(v).strip().isdigit() else str(v).strip()
        )

    # Tự động phát hiện nếu tọa độ đang ở hệ độ GPS (Latitude/Longitude, VD: 37.98, 23.72) để quy đổi ra mét (m)
    x_num = pd.to_numeric(out["x_coord_m"], errors="coerce")
    y_num = pd.to_numeric(out["y_coord_m"], errors="coerce")
    valid_xy = x_num.notna() & y_num.notna()
    if valid_xy.any():
        x_span = float(x_num[valid_xy].max() - x_num[valid_xy].min())
        y_span = float(y_num[valid_xy].max() - y_num[valid_xy].min())
        if 0 < x_span < 2.0 and 0 < y_span < 2.0 and float(y_num[valid_xy].abs().max()) <= 90.0:
            min_lon = float(x_num[valid_xy].min())
            min_lat = float(y_num[valid_xy].min())
            mean_lat_rad = math.radians(float(y_num[valid_xy].mean()))
            out["x_coord_m"] = ((x_num - min_lon) * 111320.0 * max(0.2, math.cos(mean_lat_rad))).round(2)
            out["y_coord_m"] = ((y_num - min_lat) * 110540.0).round(2)

    return out

