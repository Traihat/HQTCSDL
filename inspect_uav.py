
import zipfile
import csv
import io
import os

csv.field_size_limit(2**31 - 1)

zip_path = (
    r"D:\UAV_Traffic_Project\data\raw"
    r"\20181029_dX_0830_0900.zip"
)

with zipfile.ZipFile(zip_path, "r") as archive:
    csv_name = next(
        name for name in archive.namelist()
        if name.lower().endswith(".csv")
    )

    with archive.open(csv_name) as raw:
        stream = io.TextIOWrapper(
            raw,
            encoding="utf-8-sig",
            errors="replace",
            newline=""
        )

        reader = csv.reader(stream, delimiter=";")
        header = next(reader)
        row = next(reader)

        # Bỏ các khoảng trắng thừa quanh tên cột và giá trị
        header = [x.strip() for x in header]
        row = [x.strip() for x in row]

        # Bốn trường đầu là thông tin phương tiện
        metadata = row[:4]
        trajectory = row[4:]

        # Một trường rỗng cuối dòng có thể là dấu ; cuối cùng
        if trajectory and trajectory[-1] == "":
            trajectory = trajectory[:-1]

        print("=== THÔNG TIN PHƯƠNG TIỆN ===")
        for name, value in zip(header[:4], metadata):
            print(f"{name}: {value}")

        print("\n=== KIỂM TRA QUỸ ĐẠO ===")
        print("Số trường quỹ đạo:", len(trajectory))
        print("Chia hết cho 6:", len(trajectory) % 6 == 0)

        if len(trajectory) % 6 != 0:
            print(
                "CẢNH BÁO: Số trường không chia hết cho 6."
            )
            print("Cần kiểm tra lại cấu trúc dòng CSV.")
        else:
            point_count = len(trajectory) // 6
            print("Số điểm quỹ đạo dự kiến:", point_count)

            fields = [
                "lat", "lon", "speed",
                "lon_acc", "lat_acc", "time"
            ]

            print("\n=== 3 ĐIỂM ĐẦU TIÊN ===")
            for i in range(min(3, point_count)):
                start = i * 6
                point = trajectory[start:start + 6]
                print(
                    f"Điểm {i + 1}:",
                    dict(zip(fields, point))
                )

            print("\n=== ĐIỂM CUỐI CÙNG ===")
            start = (point_count - 1) * 6
            point = trajectory[start:start + 6]
            print(dict(zip(fields, point)))

print("\nHoàn tất kiểm tra.")
