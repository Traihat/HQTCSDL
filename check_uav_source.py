
import csv
import zipfile
import io
from pathlib import Path

zip_path = Path(
    r"D:\UAV_Traffic_Project\data\raw\20181029_dX_0830_0900.zip"
)

if not zip_path.exists():
    print("KHONG TIM THAY FILE ZIP:", zip_path)
    raise SystemExit(1)

total_vehicles = 0
total_points = 0
vehicle_ids = set()
invalid_rows = 0

with zipfile.ZipFile(zip_path, "r") as zf:
    csv_files = [
        name for name in zf.namelist()
        if name.lower().endswith(".csv")
    ]

    if not csv_files:
        print("Khong tim thay CSV trong file ZIP.")
        raise SystemExit(1)

    csv_name = csv_files[0]
    print("Dang doc:", csv_name)

    with zf.open(csv_name, "r") as raw:
        text_file = io.TextIOWrapper(
            raw, encoding="utf-8-sig", newline=""
        )
        reader = csv.reader(text_file, delimiter=";")

        header = next(reader, None)
        print("Header:", header)

        for row in reader:
            if not row or not row[0].strip():
                continue

            try:
                track_id = int(row[0].strip())

                # Bo cac cot rong o cuoi dong
                while row and row[-1].strip() == "":
                    row.pop()

                # 4 cot metadata, sau do la cac nhom 6 cot
                remaining = len(row) - 4

                if remaining < 0 or remaining % 6 != 0:
                    invalid_rows += 1
                    continue

                point_count = remaining // 6

                vehicle_ids.add(track_id)
                total_vehicles += 1
                total_points += point_count

            except (ValueError, IndexError):
                invalid_rows += 1

            if total_vehicles > 0 and total_vehicles % 500 == 0:
                print(
                    f"Da doc {total_vehicles:,} phuong tien; "
                    f"{total_points:,} diem"
                )

print("\n===== KET QUA CSV GOC =====")
print("So dong phuong tien:", f"{total_vehicles:,}")
print("So TrackID khac nhau:", f"{len(vehicle_ids):,}")
print("Tong diem:", f"{total_points:,}")
print("Dong loi:", f"{invalid_rows:,}")
