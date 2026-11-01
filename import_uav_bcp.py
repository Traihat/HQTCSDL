
import csv
import io
import os
import subprocess
import tempfile
import zipfile

import pyodbc


ZIP_PATH = (
    r"D:\UAV_Traffic_Project\data\raw"
    r"\20181029_dX_0830_0900.zip"
)

SERVER = r"localhost"
DATABASE = "UAVTrafficDB"
DATASET_ID = 1
VERSION_ID = 1

# Chi chay thu 100 dong phuong tien dau tien.
MAX_VEHICLES = 10000

# So diem quy dao trong moi file BCP.
CHUNK_SIZE = 50000

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def to_text(value):
    """Chuan hoa gia tri rong thanh chuoi rong."""
    if value is None:
        return ""
    return str(value).strip()


def main():
    if not os.path.isfile(ZIP_PATH):
        raise FileNotFoundError(ZIP_PATH)

    connection = pyodbc.connect(
        CONNECTION_STRING,
        autocommit=False,
    )
    cursor = connection.cursor()

    csv.field_size_limit(2**31 - 1)

    vehicles_read = 0
    points_written = 0
    points_loaded = 0

    # File tam chua toi da CHUNK_SIZE diem.
    with tempfile.TemporaryDirectory(
        prefix="uav_bcp_"
    ) as temp_dir:

        def import_chunk(path, count):
            nonlocal points_loaded

            if count == 0:
                return

            print(
                f"BCP dang nap {count:,} diem vao staging..."
            )

            command = [
    "bcp",
    "dbo.TrajectoryImportStage",
    "in",
    path,
    "-S", SERVER,
    "-d", DATABASE,
    "-T",
    "-u",                 # Tin cay chung chi SQL Server
    "-c",
    "-C", "65001",
    "-t", "\t",
    "-r", "\n",
    "-b", "50000",
]

            subprocess.run(command, check=True)

            # Chen cac diem chua ton tai vao bang chinh.
            # TRY_CONVERT giup kiem tra cac gia tri so.
            cursor.execute(
                """
                ;WITH Converted AS
                (
                    SELECT
                        TRY_CONVERT(INT, TrackIDText) AS TrackID,
                        VehicleTypeText AS VehicleType,
                        TRY_CONVERT(FLOAT, TimeOffsetText)
                            AS TimeOffsetSeconds,
                        TRY_CONVERT(FLOAT, LatitudeText)
                            AS Latitude,
                        TRY_CONVERT(FLOAT, LongitudeText)
                            AS Longitude,
                        TRY_CONVERT(FLOAT, SpeedText)
                            AS Speed,
                        TRY_CONVERT(FLOAT, LongitudeAccelerationText)
                            AS LongitudeAcceleration,
                        TRY_CONVERT(FLOAT, LatitudeAccelerationText)
                            AS LatitudeAcceleration,
                        TRY_CONVERT(FLOAT, TraveledDistanceText)
                            AS TraveledDistance,
                        TRY_CONVERT(FLOAT, AverageSpeedText)
                            AS AverageSpeed
                    FROM dbo.TrajectoryImportStage
                ),
                Deduplicated AS
                (
                    SELECT *,
                        ROW_NUMBER() OVER (
                            PARTITION BY TrackID, TimeOffsetSeconds
                            ORDER BY TrackID
                        ) AS rn
                    FROM Converted
                    WHERE TrackID IS NOT NULL
                      AND TimeOffsetSeconds IS NOT NULL
                )
                INSERT INTO dbo.TrajectoryRecords
                (
                    DatasetID, VersionID, ZoneID, LaneID,
                    TrackID, VehicleType, TimeOffsetSeconds,
                    Latitude, Longitude, Speed,
                    LongitudeAcceleration, LatitudeAcceleration,
                    TraveledDistance, AverageSpeed
                )
                SELECT
                    ?, ?, NULL, NULL,
                    s.TrackID, s.VehicleType, s.TimeOffsetSeconds,
                    s.Latitude, s.Longitude, s.Speed,
                    s.LongitudeAcceleration, s.LatitudeAcceleration,
                    s.TraveledDistance, s.AverageSpeed
                FROM Deduplicated AS s
                WHERE s.rn = 1
                  AND NOT EXISTS
                  (
                      SELECT 1
                      FROM dbo.TrajectoryRecords AS t
                      WHERE t.DatasetID = ?
                        AND t.VersionID = ?
                        AND t.TrackID = s.TrackID
                        AND t.TimeOffsetSeconds = s.TimeOffsetSeconds
                  );
                """,
                DATASET_ID,
                VERSION_ID,
                DATASET_ID,
                VERSION_ID,
            )

            inserted = cursor.rowcount
            connection.commit()

            # Xoa staging sau khi da commit thanh cong.
            cursor.execute(
                "TRUNCATE TABLE dbo.TrajectoryImportStage;"
            )
            connection.commit()

            points_loaded += max(inserted, 0)

            print(
                f"Da xu ly {count:,} diem; "
                f"so diem moi chen: {max(inserted, 0):,}"
            )

            os.remove(path)

        with zipfile.ZipFile(ZIP_PATH, "r") as archive:
            csv_names = [
                name for name in archive.namelist()
                if name.lower().endswith(".csv")
            ]

            if not csv_names:
                raise RuntimeError("ZIP khong co file CSV.")

            with archive.open(csv_names[0], "r") as raw:
                with io.TextIOWrapper(
                    raw,
                    encoding="utf-8-sig",
                    errors="replace",
                    newline="",
                ) as text:

                    reader = csv.reader(text, delimiter=";")
                    header = next(reader, None)

                    if not header or [
                        x.strip() for x in header[:10]
                    ] != [
                        "track_id", "type", "traveled_d",
                        "avg_speed", "lat", "lon", "speed",
                        "lon_acc", "lat_acc", "time",
                    ]:
                        raise RuntimeError(
                            "Header CSV khong dung dinh dang."
                        )

                    chunk_number = 0
                    chunk_count = 0
                    temp_path = os.path.join(
                        temp_dir, "chunk.tsv"
                    )
                    output = open(
                        temp_path,
                        "w",
                        encoding="utf-8",
                        newline="",
                    )

                    try:
                        writer = csv.writer(
                            output,
                            delimiter="\t",
                            lineterminator="\n",
                            quoting=csv.QUOTE_MINIMAL,
                        )

                        for row in reader:
                            if not row or not any(
                                x.strip() for x in row
                            ):
                                continue

                            vehicles_read += 1

                            if vehicles_read > MAX_VEHICLES:
                                break

                            metadata = [
                                to_text(row[0]),
                                to_text(row[1]),
                                to_text(row[2]),
                                to_text(row[3]),
                            ]

                            values = row[4:]

                            while (
                                values
                                and values[-1].strip() == ""
                            ):
                                values.pop()

                            if len(values) % 6 != 0:
                                raise ValueError(
                                    f"Dong CSV {vehicles_read + 1} "
                                    "khong co du 6 cot moi diem."
                                )

                            for i in range(0, len(values), 6):
                                lat, lon, speed, lon_acc, lat_acc, t = (
                                    values[i:i + 6]
                                )

                                writer.writerow([
                                    metadata[0],
                                    metadata[1],
                                    to_text(t),
                                    to_text(lat),
                                    to_text(lon),
                                    to_text(speed),
                                    to_text(lon_acc),
                                    to_text(lat_acc),
                                    metadata[2],
                                    metadata[3],
                                ])

                                chunk_count += 1
                                points_written += 1

                                if chunk_count >= CHUNK_SIZE:
                                    output.close()
                                    import_chunk(
                                        temp_path, chunk_count
                                    )

                                    chunk_number += 1
                                    chunk_count = 0
                                    temp_path = os.path.join(
                                        temp_dir,
                                        f"chunk_{chunk_number}.tsv",
                                    )
                                    output = open(
                                        temp_path,
                                        "w",
                                        encoding="utf-8",
                                        newline="",
                                    )
                                    writer = csv.writer(
                                        output,
                                        delimiter="\t",
                                        lineterminator="\n",
                                        quoting=csv.QUOTE_MINIMAL,
                                    )

                    finally:
                        if not output.closed:
                            output.close()

                    if chunk_count:
                        import_chunk(temp_path, chunk_count)

    cursor.close()
    connection.close()

    print("\n===== KET QUA CHAY THU =====")
    print("So dong phuong tien da doc:", vehicles_read)
    print("So diem da chuyen doi:", f"{points_written:,}")
    print("So diem moi da chen:", f"{points_loaded:,}")
    print("Hoan tat chay thu.")


if __name__ == "__main__":
    main()

