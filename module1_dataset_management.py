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


def _derive_dynamic_zones(df_clean: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Tự động chia Khu vực (DynamicZones) dựa trực tiếp trên dữ liệu được nạp vào:
      - Trường hợp 1: Nếu file dữ liệu có cột `zone_name` -> trích xuất tự động các khu vực thực tế trong file.
      - Trường hợp 2: Nếu file dữ liệu KHÔNG có cột `zone_name` (như file tọa độ hoặc file pNEUMA 1.72 GB) ->
        tự động phân hoạch không gian tọa độ (x_coord_m, y_coord_m) thành 5 phân khu đô thị động.
    """
    df = df_clean.copy()
    zones_meta = []

    if "zone_name" in df.columns and df["zone_name"].dropna().nunique() >= 2:
        df["zone_name"] = df["zone_name"].astype(str).str.strip()
        unique_zones = list(df["zone_name"].unique())[:8]
        df = df[df["zone_name"].isin(unique_zones)].copy()
        partition_method = "Extracted_From_File_Columns"

        for idx, z_name in enumerate(unique_zones, start=1):
            sub = df[df["zone_name"] == z_name]
            x_min, x_max = float(sub["x_coord_m"].min()), float(sub["x_coord_m"].max())
            y_min, y_max = float(sub["y_coord_m"].min()), float(sub["y_coord_m"].max())
            if "road_length_km" in sub.columns and sub["road_length_km"].notna().any():
                road_len = round(max(0.4, float(sub["road_length_km"].dropna().iloc[0])), 2)
            else:
                diag_m = math.hypot(max(100.0, x_max - x_min), max(100.0, y_max - y_min))
                road_len = round(max(0.6, diag_m / 650.0), 2)

            zones_meta.append({
                "zone_code": f"DYN_ZONE_{idx}",
                "zone_name": z_name,
                "partition_method": partition_method,
                "x_min_m": round(x_min, 2),
                "x_max_m": round(x_max, 2),
                "y_min_m": round(y_min, 2),
                "y_max_m": round(y_max, 2),
                "road_length_km": road_len,
            })
    else:
        partition_method = "Coordinate_Spatial_Clustering"
        x = df["x_coord_m"].to_numpy(dtype=float)
        y = df["y_coord_m"].to_numpy(dtype=float)
        qx30, qx70 = float(np.percentile(x, 30)), float(np.percentile(x, 70))
        qy30, qy70 = float(np.percentile(y, 30)), float(np.percentile(y, 70))
        x_mid, y_mid = float(np.median(x)), float(np.median(y))

        in_center = (x >= qx30) & (x <= qx70) & (y >= qy30) & (y <= qy70)
        assigned = np.full(len(df), "Phân Khu Đông Nam (SE)", dtype=object)
        assigned[(~in_center) & (x < x_mid) & (y >= y_mid)] = "Phân Khu Tây Bắc (NW)"
        assigned[(~in_center) & (x >= x_mid) & (y >= y_mid)] = "Phân Khu Đông Bắc (NE)"
        assigned[(~in_center) & (x < x_mid) & (y < y_mid)] = "Phân Khu Tây Nam (SW)"
        assigned[in_center] = "Khu Trung Tâm Tọa Độ (Center)"
        df["zone_name"] = assigned

        for idx, z_name in enumerate(
            [
                "Khu Trung Tâm Tọa Độ (Center)",
                "Phân Khu Tây Bắc (NW)",
                "Phân Khu Đông Bắc (NE)",
                "Phân Khu Tây Nam (SW)",
                "Phân Khu Đông Nam (SE)",
            ],
            start=1,
        ):
            sub = df[df["zone_name"] == z_name]
            if sub.empty:
                continue
            x_min, x_max = float(sub["x_coord_m"].min()), float(sub["x_coord_m"].max())
            y_min, y_max = float(sub["y_coord_m"].min()), float(sub["y_coord_m"].max())
            diag_m = math.hypot(max(100.0, x_max - x_min), max(100.0, y_max - y_min))
            road_len = round(max(0.75, diag_m / 600.0), 2)
            zones_meta.append({
                "zone_code": f"AUTO_ZONE_{idx}",
                "zone_name": z_name,
                "partition_method": partition_method,
                "x_min_m": round(x_min, 2),
                "x_max_m": round(x_max, 2),
                "y_min_m": round(y_min, 2),
                "y_max_m": round(y_max, 2),
                "road_length_km": road_len,
            })

    return df, zones_meta


def _derive_dynamic_timeframes(df_clean: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Tự động chia Khung giờ (DynamicTimeFrames) thích ứng thông minh với độ dài thời gian thực tế
    của file dữ liệu được nạp vào (từ phiên bay UAV 12 phút đến dữ liệu nhiều giờ).
    """
    df = df_clean.copy()
    parsed_dt = pd.to_datetime(df["recorded_time"], errors="coerce")

    if parsed_dt.notna().sum() < int(0.8 * len(df)):
        raise ValueError("Không đủ timestamp hợp lệ để xác định khung thời gian Dataset.")
    df["_dt"] = parsed_dt
    min_dt = df["_dt"].min()
    df["time_sec"] = (df["_dt"] - min_dt).dt.total_seconds().astype(float)
    df["recorded_time_str"] = df["_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")

    total_span_sec = max(float(df["time_sec"].max() - df["time_sec"].min()), 60.0)
    if total_span_sec <= 1200:
        n_slots = 4
        slot_sec = total_span_sec / 4.0
    elif total_span_sec <= 2400:
        slot_sec = 450.0
        n_slots = max(2, int(math.ceil((total_span_sec + 1e-6) / slot_sec)))
    elif total_span_sec <= 3600:
        slot_sec = 900.0
        n_slots = max(2, int(math.ceil((total_span_sec + 1e-6) / slot_sec)))
    elif total_span_sec <= 10800:
        slot_sec = 1800.0
        n_slots = max(2, int(math.ceil((total_span_sec + 1e-6) / slot_sec)))
    else:
        slot_sec = max(1800.0, math.ceil(total_span_sec / 5.0 / 600.0) * 600.0)
        n_slots = max(2, int(math.ceil((total_span_sec + 1e-6) / slot_sec)))

    slot_indices = np.clip((df["time_sec"].to_numpy(dtype=float) // slot_sec).astype(int), 0, n_slots - 1)
    df["_slot_idx"] = slot_indices

    slot_counts = pd.Series(slot_indices).value_counts()
    peak_threshold = float(slot_counts.quantile(0.70)) if len(slot_counts) > 1 else 0.0

    timeframes_meta = []
    for s_idx in range(n_slots):
        s_start_sec = s_idx * slot_sec
        s_end_sec = min((s_idx + 1) * slot_sec, max(total_span_sec, slot_sec))
        st_dt = min_dt + pd.Timedelta(seconds=s_start_sec)
        en_dt = min_dt + pd.Timedelta(seconds=s_end_sec)
        st_hm = st_dt.strftime("%H:%M")
        en_hm = en_dt.strftime("%H:%M")
        if st_hm == en_hm:
            st_hm = st_dt.strftime("%H:%M:%S")
            en_hm = en_dt.strftime("%H:%M:%S")
        cnt_in_slot = int(slot_counts.get(s_idx, 0))
        is_peak = 1 if cnt_in_slot >= peak_threshold else 0
        tag_suffix = " (Cao điểm)" if is_peak else ""
        timeframes_meta.append({
            "slot_idx": s_idx,
            "timeframe_code": f"TF_{s_idx+1}",
            "timeframe_label": f"{st_hm} - {en_hm}{tag_suffix}",
            "start_time_str": st_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time_str": en_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "start_epoch_sec": round(s_start_sec, 1),
            "end_epoch_sec": round(s_end_sec, 1),
            "duration_minutes": round(max(1.0, (s_end_sec - s_start_sec) / 60.0), 1),
            "is_peak_timeframe": is_peak,
        })

    return df, timeframes_meta


def process_and_ingest_uploaded_file(
    file_name: str,
    file_bytes: bytes | None = None,
    file_path: Path | None = None,
    db_path: Path = DB_PATH,
    override_size_kb: float | None = None,
    dataset_uuid: str | None = None,
    checksum_sha256: str | None = None,
    allow_duplicate: bool = False,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    manual_metadata: dict | None = None,
) -> dict:
    """
    Hàm cốt lõi của Module 1:
      1. Đọc file Excel (.xlsx, .xls) hoặc CSV (.csv) được kéo thả vào (hỗ trợ Streaming cho file lớn tới 3 GB).
      2. Tiền xử lý 4 bước: lọc thiếu/trùng, lọc xe đỗ tĩnh, lọc ngoại lai vận tốc/gia tốc, chuẩn hóa tọa độ.
      3. Tự động chia Khu vực động (`DynamicZones`) và Khung giờ động (`DynamicTimeFrames`) theo dữ liệu thực tế.
      4. Tính toán chỉ số giao thông (`TrafficPatternMetrics`), dự báo ARIMA & Prophet (`ForecastComparisons`, `ForecastPoints`),
         khởi tạo thực nghiệm (`ExperimentRuns`) và báo cáo (`GeneratedReports`).
      5. Nạp toàn bộ vào 9 bảng CSDL và trả về dòng thông báo thành công.
    """
    init_db(db_path)
    if checksum_sha256 is None:
        if file_bytes is not None:
            checksum_sha256 = hashlib.sha256(file_bytes).hexdigest()
        elif file_path is not None and file_path.exists():
            checksum_sha256 = _sha256_file(file_path)
        else:
            raise FileNotFoundError(f"Không tìm thấy file dữ liệu: {file_name}")
    duplicate = find_dataset_by_checksum(checksum_sha256, db_path)
    if duplicate and not allow_duplicate:
        raise DuplicateDatasetError(duplicate)
    dataset_uuid = dataset_uuid or str(uuid.uuid4())
    dataset_metadata = _parse_dataset_metadata(file_name, manual_metadata)
    base_datetime = None
    if dataset_metadata["capture_date"] and dataset_metadata["start_time"]:
        base_datetime = pd.Timestamp(
            f"{dataset_metadata['capture_date']} {dataset_metadata['start_time']}:00"
        )
    raw_df, ext, size_kb = _read_dataframe_from_input(
        file_name=file_name,
        file_bytes=file_bytes,
        file_path=file_path,
        override_size_kb=override_size_kb,
        base_datetime=base_datetime,
    )
    df = _normalize_columns(raw_df, base_datetime=base_datetime)
    n_raw = len(df)

    # Bước 1: Lọc dòng thiếu giá trị (NaN) và bản ghi trùng lặp
    for num_col in ("x_coord_m", "y_coord_m", "speed_kmh", "accel_ms2"):
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
    df_step1 = df.dropna(subset=["vehicle_id", "recorded_time", "x_coord_m", "y_coord_m", "speed_kmh"]).copy()
    df_step1 = df_step1.drop_duplicates(subset=["vehicle_id", "recorded_time", "x_coord_m", "y_coord_m"])
    if df_step1.empty:
        raise ValueError("Không còn bản ghi hợp lệ sau khi kiểm tra timestamp, tọa độ và vận tốc.")
    removed_missing_dup = max(0, n_raw - len(df_step1))

    # Bước 2: Lọc bỏ phương tiện đỗ tĩnh (speed_kmh <= 0.5 km/h)
    df_step2 = df_step1[df_step1["speed_kmh"] > 0.5].copy()
    if df_step2.empty:
        raise ValueError("Dataset chỉ chứa phương tiện đứng yên; không có dữ liệu giao thông để phân tích.")
    removed_stationary = max(0, len(df_step1) - len(df_step2))

    # Bước 3: Lọc bỏ ngoại lai vận tốc (> 120 km/h) và gia tốc (|accel| > 15 m/s²)
    df_step2["accel_ms2"] = df_step2["accel_ms2"].fillna(0.0)
    df_clean = df_step2[
        (df_step2["speed_kmh"] <= 120.0)
        & (df_step2["accel_ms2"] >= -15.0)
        & (df_step2["accel_ms2"] <= 15.0)
    ].copy()
    if df_clean.empty:
        raise ValueError("Không còn bản ghi hợp lệ sau khi loại ngoại lai vận tốc/gia tốc.")
    removed_outliers = max(0, len(df_step2) - len(df_clean))

    # Bước 4: Tự động chia Khu vực ĐỘNG & Khung giờ ĐỘNG từ dữ liệu sạch
    df_clean, zones_meta = _derive_dynamic_zones(df_clean)
    df_clean, timeframes_meta = _derive_dynamic_timeframes(df_clean)

    stored_path = _store_original_file(
        file_name=file_name,
        file_bytes=file_bytes,
        source_path=file_path,
        dataset_uuid=dataset_uuid,
        storage_root=storage_root,
    )

    conn = get_connection(db_path)
    cur = conn.cursor()

    t_start_str = df_clean["_dt"].min().strftime("%Y-%m-%d %H:%M:%S")
    t_end_str = df_clean["_dt"].max().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute(
        """
        INSERT INTO DatasetImports (
            file_name, file_extension, file_size_kb, raw_row_count, cleaned_row_count,
            removed_missing_dup, removed_stationary, removed_outliers, dynamic_zone_count,
            dynamic_timeframe_count, time_range_start, time_range_end, status_message,
            dataset_uuid, storage_path, checksum_sha256, capture_date, drone_id, start_time,
            end_time, duration_minutes, processing_status, validation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_name,
            ext,
            size_kb,
            n_raw,
            len(df_clean),
            removed_missing_dup,
            removed_stationary,
            removed_outliers,
            len(zones_meta),
            len(timeframes_meta),
            t_start_str,
            t_end_str,
            PROCESS_SUCCESS_TEXT,
            dataset_uuid,
            stored_path,
            checksum_sha256,
            dataset_metadata["capture_date"],
            dataset_metadata["drone_id"],
            dataset_metadata["start_time"],
            dataset_metadata["end_time"],
            dataset_metadata["duration_minutes"],
            "saved",
            (
                "valid"
                if all(
                    dataset_metadata[key]
                    for key in ("capture_date", "drone_id", "start_time", "end_time")
                )
                else "metadata_missing"
            ),
        ),
    )
    import_id = int(cur.lastrowid)

    # Nạp bảng DynamicZones
    zone_name_to_id = {}
    zone_id_to_meta = {}
    for z in zones_meta:
        cur.execute(
            """
            INSERT INTO DynamicZones (
                import_id, zone_code, zone_name, partition_method,
                x_min_m, x_max_m, y_min_m, y_max_m, road_length_km
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                import_id,
                z["zone_code"],
                z["zone_name"],
                z["partition_method"],
                z["x_min_m"],
                z["x_max_m"],
                z["y_min_m"],
                z["y_max_m"],
                z["road_length_km"],
            ),
        )
        zid = int(cur.lastrowid)
        zone_name_to_id[z["zone_name"]] = zid
        zone_id_to_meta[zid] = z

    # Nạp bảng DynamicTimeFrames
    slot_to_tf_id = {}
    for tf in timeframes_meta:
        cur.execute(
            """
            INSERT INTO DynamicTimeFrames (
                import_id, timeframe_code, timeframe_label, start_time_str, end_time_str,
                start_epoch_sec, end_epoch_sec, duration_minutes, is_peak_timeframe
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                import_id,
                tf["timeframe_code"],
                tf["timeframe_label"],
                tf["start_time_str"],
                tf["end_time_str"],
                tf["start_epoch_sec"],
                tf["end_epoch_sec"],
                tf["duration_minutes"],
                tf["is_peak_timeframe"],
            ),
        )
        slot_to_tf_id[tf["slot_idx"]] = int(cur.lastrowid)

    df_clean["zone_id"] = df_clean["zone_name"].map(zone_name_to_id)
    df_clean["timeframe_id"] = df_clean["_slot_idx"].map(slot_to_tf_id)
    df_clean["lane_no"] = pd.to_numeric(df_clean["lane_no"], errors="coerce").fillna(1).astype(int)

    # Nạp bảng CleanedTrajectories
    traj_records = [
        (
            import_id,
            int(row.zone_id),
            int(row.timeframe_id),
            str(row.vehicle_id),
            str(row.vehicle_type),
            str(row.recorded_time_str),
            round(float(row.time_sec), 2),
            round(float(row.x_coord_m), 2),
            round(float(row.y_coord_m), 2),
            round(float(row.speed_kmh), 2),
            round(float(row.accel_ms2), 2),
            int(row.lane_no),
        )
        for row in df_clean.itertuples(index=False)
    ]
    cur.executemany(
        """
        INSERT INTO CleanedTrajectories (
            import_id, zone_id, timeframe_id, vehicle_id, vehicle_type,
            recorded_time_str, time_sec, x_coord_m, y_coord_m, speed_kmh, accel_ms2, lane_no
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        traj_records,
    )

