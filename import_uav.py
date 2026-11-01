
import csv
import io
import os
import time
import zipfile

import pyodbc


# ============================================================
# 1. CAU HINH
# ============================================================

ZIP_PATH = (
    r"D:\UAV_Traffic_Project\data\raw"
    r"\20181029_dX_0830_0900.zip"
)

SERVER = r"localhost"
DATABASE = "UAVTrafficDB"
DATASET_ID = 1
VERSION_ID = 1

BATCH_SIZE = 500

# None = nhap TOAN BO file.
# Khong doi thanh 10 khi chay that.
MAX_VEHICLES = None


CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


INSERT_SQL = """
INSERT INTO dbo.TrajectoryRecords (
    DatasetID,
    VersionID,
    ZoneID,
    LaneID,
    TrackID,
    VehicleType,
    TimeOffsetSeconds,
    Latitude,
    Longitude,
    Speed,
    LongitudeAcceleration,
    LatitudeAcceleration,
    TraveledDistance,
    AverageSpeed
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


def optional_float(value):
    """Chuyen gia tri rong thanh NULL, gia tri khac thanh float."""
    value = value.strip()

    if value == "":
        return None

    return float(value)


def set_status(cursor, connection, status):
    """Cap nhat trang thai bo du lieu va phien ban."""
    cursor.execute(
        """
        UPDATE dbo.Datasets
        SET Status = ?
        WHERE DatasetID = ?;
        """,
        status,
        DATASET_ID,
    )

    cursor.execute(
        """
        UPDATE dbo.DatasetVersions
        SET Status = ?
        WHERE VersionID = ?
          AND DatasetID = ?;
        """,
        status,
        VERSION_ID,
        DATASET_ID,
    )

    connection.commit()


def main():
    if not os.path.isfile(ZIP_PATH):
        raise FileNotFoundError(
            f"Khong tim thay file ZIP:\n{ZIP_PATH}"
        )

    start_time = time.time()

    vehicles_read = 0
    vehicles_imported = 0
    vehicles_skipped = 0
    points_imported = 0

    print("Dang ket noi SQL Server...")

    connection = pyodbc.connect(
        CONNECTION_STRING,
        autocommit=False,
    )

    cursor = connection.cursor()
    cursor.fast_executemany = True

    try:
        # Lay danh sach TrackID da co du lieu.
        cursor.execute(
            """
            SELECT DISTINCT TrackID
            FROM dbo.TrajectoryRecords
            WHERE DatasetID = ?
              AND VersionID = ?;
            """,
            DATASET_ID,
            VERSION_ID,
        )

        existing_track_ids = {
            int(row[0]) for row in cursor.fetchall()
        }

        print(
            "So TrackID da co trong database:",
            len(existing_track_ids),
        )

        set_status(cursor, connection, "IMPORTING")

        csv.field_size_limit(2**31 - 1)

        print("Dang mo CSV trong ZIP...")
        print("Qua trinh co the mat nhieu thoi gian.")

        with zipfile.ZipFile(ZIP_PATH, "r") as zip_file:
            csv_files = [
                name
                for name in zip_file.namelist()
                if name.lower().endswith(".csv")
            ]

            if not csv_files:
                raise RuntimeError(
                    "Khong tim thay file CSV trong ZIP."
                )

            # Dataset nay du kien chi co mot CSV.
            csv_name = csv_files[0]

            print("File CSV:", csv_name)

            with zip_file.open(csv_name, "r") as raw_file:
                with io.TextIOWrapper(
                    raw_file,
                    encoding="utf-8-sig",
                    errors="replace",
                    newline="",
                ) as text_file:

                    reader = csv.reader(
                        text_file,
                        delimiter=";",
                    )

                    header = next(reader, None)

                    if not header:
                        raise RuntimeError(
                            "File CSV rong hoac khong co header."
                        )

                    header = [value.strip() for value in header]

                    expected_header = [
                        "track_id",
                        "type",
                        "traveled_d",
                        "avg_speed",
                        "lat",
                        "lon",
                        "speed",
                        "lon_acc",
                        "lat_acc",
                        "time",
                    ]

                    if header[:len(expected_header)] != expected_header:
                        raise RuntimeError(
                            "Header CSV khong dung dinh dang du kien.\n"
                            f"Header doc duoc: {header[:10]}"
                        )

                    seen_source_ids = set()

                    for row in reader:
                        if not row or not any(
                            value.strip() for value in row
                        ):
                            continue

                        vehicles_read += 1

                        if (
                            MAX_VEHICLES is not None
                            and vehicles_read > MAX_VEHICLES
                        ):
                            break

                        try:
                            # Bon cot metadata dau tien.
                            track_id = int(row[0].strip())
                            vehicle_type = row[1].strip()

                            traveled_distance = optional_float(row[2])
                            average_speed = optional_float(row[3])

                            # Phat hien TrackID lap trong cung file.
                            if track_id in seen_source_ids:
                                vehicles_skipped += 1
                                continue

                            seen_source_ids.add(track_id)

                            # Bo cac cot rong o cuoi dong neu co.
                            trajectory_values = row[4:]

                            while (
                                trajectory_values
                                and trajectory_values[-1].strip() == ""
                            ):
                                trajectory_values.pop()

                            if len(trajectory_values) % 6 != 0:
                                raise ValueError(
                                    f"TrackID {track_id}: "
                                    "so cot quy dao khong chia het cho 6."
                                )

                            # Neu TrackID da nhap thanh cong truoc do,
                            # bo qua de co the tiep tuc khi chay lai.
                            if track_id in existing_track_ids:
                                vehicles_skipped += 1
                                continue

                            points = []

                            for i in range(
                                0,
                                len(trajectory_values),
                                6,
                            ):
                                lat_text = trajectory_values[i]
                                lon_text = trajectory_values[i + 1]
                                speed_text = trajectory_values[i + 2]
                                lon_acc_text = trajectory_values[i + 3]
                                lat_acc_text = trajectory_values[i + 4]
                                time_text = trajectory_values[i + 5]

                                time_offset = float(time_text.strip())

                                point = (
                                    DATASET_ID,
                                    VERSION_ID,
                                    None,  # ZoneID chua gan
                                    None,  # LaneID chua gan
                                    track_id,
                                    vehicle_type,
                                    time_offset,
                                    optional_float(lat_text),
                                    optional_float(lon_text),
                                    optional_float(speed_text),
                                    optional_float(lon_acc_text),
                                    optional_float(lat_acc_text),
                                    traveled_distance,
                                    average_speed,
                                )

                                points.append(point)

                            if not points:
                                raise ValueError(
                                    f"TrackID {track_id} khong co diem quy dao."
                                )

                            # Moi phuong tien la mot giao dich rieng.
                            # Neu loi, rollback toan bo diem cua phuong tien nay.
                            for start in range(
                                0,
                                len(points),
                                BATCH_SIZE,
                            ):
                                batch = points[
                                    start:start + BATCH_SIZE
                                ]

                                cursor.executemany(
                                    INSERT_SQL,
                                    batch,
                                )

                            connection.commit()

                            existing_track_ids.add(track_id)
                            vehicles_imported += 1
                            points_imported += len(points)

                            if vehicles_imported % 100 == 0:
                                elapsed = time.time() - start_time

                                print(
                                    f"Da nhap {vehicles_imported:,} "
                                    f"phuong tien moi | "
                                    f"{points_imported:,} diem moi | "
                                    f"{elapsed:.1f} giay"
                                )

                        except Exception as error:
                            # Huy cac thay doi chua commit cua phuong tien nay.
                            connection.rollback()

                            raise RuntimeError(
                                f"Loi khi xu ly dong CSV "
                                f"{vehicles_read + 1}, "
                                f"TrackID co the la {row[0]!r}.\n"
                                f"Chi tiet: {error}"
                            ) from error

        # Dem tong so diem trong database sau khi nhap xong.
        cursor.execute(
            """
            SELECT COUNT_BIG(*)
            FROM dbo.TrajectoryRecords
            WHERE DatasetID = ?
              AND VersionID = ?;
            """,
            DATASET_ID,
            VERSION_ID,
        )

        total_points_in_database = int(cursor.fetchone()[0])

        # RecordCount duoc tinh theo so diem quy dao.
        cursor.execute(
            """
            UPDATE dbo.DatasetVersions
            SET RecordCount = ?,
                Status = 'COMPLETED'
            WHERE VersionID = ?
              AND DatasetID = ?;
            """,
            total_points_in_database,
            VERSION_ID,
            DATASET_ID,
        )

        cursor.execute(
            """
            UPDATE dbo.Datasets
            SET Status = 'COMPLETED'
            WHERE DatasetID = ?;
            """,
            DATASET_ID,
        )

        connection.commit()

        elapsed = time.time() - start_time

        print("\n========== HOAN TAT ==========")
        print(f"Dong phuong tien da doc: {vehicles_read:,}")
        print(f"Phuong tien moi da nhap: {vehicles_imported:,}")
        print(f"Phuong tien da bo qua: {vehicles_skipped:,}")
        print(f"Diem quy dao moi da nhap: {points_imported:,}")
        print(
            "Tong diem trong database:",
            f"{total_points_in_database:,}",
        )
        print(f"Thoi gian: {elapsed:.1f} giay")
        print("Trang thai: COMPLETED")

    except Exception as error:
        connection.rollback()

        print("\n========== NHAP DU LIEU BI LOI ==========")
        print(error)

        # Cap nhat FAILED sau khi rollback giao dich bi loi.
        try:
            set_status(cursor, connection, "FAILED")
            print("Da cap nhat trang thai thanh FAILED.")
            print(
                "Sau khi sua loi, co the chay lai script. "
                "Cac phuong tien da commit se duoc bo qua."
            )
        except Exception as status_error:
            connection.rollback()
            print("Khong cap nhat duoc trang thai:", status_error)

        raise

    finally:
        cursor.close()
        connection.close()
        print("Da dong ket noi SQL Server.")


if __name__ == "__main__":
    main()
