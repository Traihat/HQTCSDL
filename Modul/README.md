# 🧩 CÁC MODULE CHỨC NĂNG PYTHON (`6_nopbai/Modul/`)
**Đề tài:** Phân tích mô hình giao thông đô thị và dự báo ùn tắc ngắn hạn sử dụng dữ liệu UAV  
**Cơ sở dữ liệu kết nối trực tiếp:** `../database/UrbanTrafficAnalyticsDB.db` (13 bảng / 5 phân hệ - chuẩn `01_init_schema.sql`)

---

## 🎯 Đặc điểm thiết kế của bộ Module trong `Modul/`
1. **Đúng chuẩn Sinh viên Năm 3 — Dễ đọc, dễ giải thích khi bảo vệ**:
   - Chỉ sử dụng các thư viện chuẩn mực quen thuộc trong `6_nopbai/requirements.txt`: `sqlite3`, `pandas`, `numpy`, `matplotlib`, `statsmodels`, `hashlib`, `json`, `pathlib`.
   - Không dùng lớp (OOP) phức tạp hay thư viện ẩn; mỗi chức năng là một hàm Python tường minh kèm câu lệnh SQL rõ ràng và chú thích tiếng Việt.
2. **Mỗi file `.py` chạy độc lập 100% hoặc tích hợp qua Menu**:
   - Bấm chạy lẻ bất kỳ file nào (`python M2_Phan_tich_mo_hinh_giao_thong.py`) để demo riêng chức năng đó.
   - Hoặc chạy `python main_chay_tat_ca_modul.py` (chạy kiểm thử toàn bộ `M0 -> M6`) và `python main_chay_tat_ca_modul.py --menu` (mở Menu tương tác khi lên vấn đáp).
3. **Bao phủ trọn vẹn 7 Module đề cương (`M0 -> M6`), 13 bảng CSDL và `FR-01 -> FR-39`**:

| Mã Module | File Python (`.py`) | Yêu cầu chức năng & RQ | Bảng CSDL tương tác | Các hàm chức năng chính |
| :---: | :--- | :--- | :--- | :--- |
| **M0** | [`M0_Quan_ly_nguoi_dung.py`](M0_Quan_ly_nguoi_dung.py) | `FR-01` → `FR-03` | `Roles`, `Users`, `UserRoles`, `AuditLogs` | `hash_password()`, `login()`, `check_permission()`, `create_user()`, `set_user_active_status()`, `assign_role()` |
| **M1** | [`M1_Quan_ly_va_Lam_sach_Dataset.py`](M1_Quan_ly_va_Lam_sach_Dataset.py) | `FR-04` → `FR-12`, `FR-39` (**RQ1**) | `Datasets`, `Tracks`, `TrajectoryPoints`, `TrafficSpatialZones`, `TrafficAggregatedMetrics` | `validate_uav_csv_schema()`, `preview_uav_csv()`, `register_dataset_version()`, `clean_and_validate_trajectories()`, `archive_dataset()`, `delete_dataset()` |
| **M2** | [`M2_Phan_tich_mo_hinh_giao_thong.py`](M2_Phan_tich_mo_hinh_giao_thong.py) | `FR-13` → `FR-17` (**RQ1, RQ4**) | `TrafficSpatialZones`, `TrafficAggregatedMetrics`, `Tracks`, `TrajectoryPoints` | `get_available_zones_and_intervals()`, `get_zone_timeseries()`, `summarize_traffic_by_zone()`, `detect_peak_periods()`, `analyze_congestion_distribution()`, `identify_congestion_hotspots()` |
| **M3** | [`M3_Du_bao_ngan_han.py`](M3_Du_bao_ngan_han.py) | `FR-18` → `FR-24` (**RQ2, RQ3**) | `TrafficAggregatedMetrics`, `TrafficSpatialZones` | `extract_density_timeseries()`, `forecast_naive_baseline()`, `forecast_arima()` *(thủ công & auto AIC)*, `forecast_prophet()`, `evaluate_forecast()`, `compare_models_across_intervals()`, `plot_forecast_results()` |
| **M4** | [`M4_Dashboard_truc_quan.py`](M4_Dashboard_truc_quan.py) | `FR-25` → `FR-28`, `FR-38` (**RQ4**) | Toàn bộ các bảng phân tích & dự báo | `get_dashboard_kpis()`, `get_online_help_glossary()`, `plot_spatial_heatmap()`, `generate_full_dashboard()` |
| **M5** | [`M5_Quan_ly_thuc_nghiem.py`](M5_Quan_ly_thuc_nghiem.py) | `FR-29` → `FR-32` (**RQ2, RQ3**) | `Experiments`, `ForecastEvaluations`, `ForecastResults`, `Datasets` | `create_and_run_experiment()`, `list_experiments()`, `pivot_experiments_rq2_rq3()`, `reproduce_experiment()`, `plot_experiment_comparison()` |
| **M6** | [`M6_Bao_cao_va_Audit_Log.py`](M6_Bao_cao_va_Audit_Log.py) | `FR-33` → `FR-37` | `Reports`, `AuditLogs`, `Users` | `export_traffic_pattern_csv()`, `export_forecast_comparison_csv()`, `export_executive_summary_pdf()`, `write_audit_log()`, `query_audit_logs()` |

---

## 🗂️ Cấu trúc thư mục `6_nopbai/Modul/`

```text
Modul/
├── README.md                              # Tài liệu hướng dẫn nhanh & bảng ánh xạ 7 Module <-> 13 Bảng SQL
├── Giai_Thich_Chi_Tiet_Cac_Modul.md       # Tài liệu giải thích chi tiết từng hàm, SQL, công thức toán & 12 câu hỏi vấn đáp
├── M0_Quan_ly_nguoi_dung.py               # Module 0: Xác thực SHA-256 & Phân quyền RBAC 4 vai trò
├── M1_Quan_ly_va_Lam_sach_Dataset.py      # Module 1: Kiểm tra Schema, Quản lý phiên bản & Làm sạch UAV 4 bước
├── M2_Phan_tich_mo_hinh_giao_thong.py     # Module 2: Lưu lượng q=k*v, Cao điểm, 4 Mức ùn tắc & Spatial Hotspots
├── M3_Du_bao_ngan_han.py                  # Module 3: Dự báo Naive, ARIMA (thủ công/auto AIC), Prophet & Đánh giá
├── M4_Dashboard_truc_quan.py              # Module 4: Bảng KPI tổng quan, Glossary & Dashboard 6 biểu đồ + Heatmap
├── M5_Quan_ly_thuc_nghiem.py              # Module 5: Lưu cấu hình thực nghiệm, So sánh RQ2/RQ3 & Kiểm chứng tái lập
├── M6_Bao_cao_va_Audit_Log.py             # Module 6: Xuất báo cáo CSV (Excel), PDF 2 trang & Nhật ký AuditLogs
├── main_chay_tat_ca_modul.py              # Chương trình chạy tích hợp cả 7 Module hoặc mở Menu vấn đáp (--menu)
└── outputs/                               # Thư mục tự động lưu biểu đồ (.png) và báo cáo (.csv, .pdf)
    ├── M3_du_bao_so_sanh_mo_hinh.png
    ├── M4_dashboard_tong_quan_6_bieu_do.png
    ├── M4_heatmap_khong_gian_va_vung.png
    ├── M5_so_sanh_thuc_nghiem.png
    ├── M6_Bao_Cao_Phan_Tich_Giao_Thong.csv
    ├── M6_Bao_Cao_So_Sanh_Du_Bao.csv
    └── M6_Bao_Cao_Tong_Hop_Giao_Thong_Va_Du_Bao.pdf
```

---

## 🚀 Hướng dẫn Chạy trên Máy tính

Mở Terminal / PowerShell tại thư mục `E:\tailieu\HQTCSDL\1_BA\6_nopbai\Modul` (sử dụng môi trường Python đã cài các gói trong `../requirements.txt`, ví dụ `.venv` của dự án):

```powershell
# 1. Chạy kiểm thử tự động toàn bộ 7 Module (M0 -> M6) và kiểm tra toàn vẹn 13 bảng CSDL:
python main_chay_tat_ca_modul.py

# 2. Mở Menu tương tác để chọn chạy từng Module khi trình bày trước giảng viên:
python main_chay_tat_ca_modul.py --menu

# 3. Hoặc chạy độc lập bất kỳ Module riêng lẻ nào:
python M0_Quan_ly_nguoi_dung.py
python M1_Quan_ly_va_Lam_sach_Dataset.py
python M2_Phan_tich_mo_hinh_giao_thong.py
python M3_Du_bao_ngan_han.py
python M4_Dashboard_truc_quan.py
python M5_Quan_ly_thuc_nghiem.py
python M6_Bao_cao_va_Audit_Log.py
```
