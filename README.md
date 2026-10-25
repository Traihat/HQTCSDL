## Hướng dẫn cài đặt Cơ sở dữ liệu
1. Mở SQL Server Management Studio (SSMS).
2. Mở file `database/01_init_schema.sql` và bấm `F5` để khởi tạo database `UrbanTrafficAnalyticsDB`.
3. Chạy file `database/02_seed_data.sql` để tạo tài khoản admin và metadata mẫu.
4. Chạy script `python etl/import_data.py` để nạp dữ liệu trajectory từ UAV.
