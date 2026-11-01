"""
CHƯƠNG TRÌNH TÍCH HỢP & KIỂM THỬ TOÀN BỘ 7 MODULE CHỨC NĂNG (M0 -> M6)
======================================================================
Đề tài: Phân tích mô hình giao thông đô thị và dự báo ùn tắc ngắn hạn sử dụng dữ liệu UAV
CSDL  : database/UrbanTrafficAnalyticsDB.db (13 bảng / 5 phân hệ)

Cách sử dụng:
  1. Chạy tự động kiểm thử toàn bộ 7 module (M0 -> M6) + kiểm tra 13 bảng CSDL:
       python main_chay_tat_ca_modul.py
  2. Mở Menu tương tác chọn chạy từng module khi bảo vệ / vấn đáp đồ án:
       python main_chay_tat_ca_modul.py --menu
"""

import sqlite3
import sys
import time
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MODUL_DIR = Path(__file__).resolve().parent
if str(MODUL_DIR) not in sys.path:
    sys.path.insert(0, str(MODUL_DIR))

import M0_Quan_ly_nguoi_dung as M0
import M1_Quan_ly_va_Lam_sach_Dataset as M1
import M2_Phan_tich_mo_hinh_giao_thong as M2
import M3_Du_bao_ngan_han as M3
import M4_Dashboard_truc_quan as M4
import M5_Quan_ly_thuc_nghiem as M5
import M6_Bao_cao_va_Audit_Log as M6

DB_PATH = MODUL_DIR.parent / "database" / "UrbanTrafficAnalyticsDB.db"

MODULES_REGISTRY = [
    ("0", "M0 - Quản lý Người dùng & Phân quyền RBAC (FR-01..03)", M0.run_demo),
    ("1", "M1 - Quản lý Dataset & Làm sạch Quỹ đạo UAV (FR-04..12, FR-39)", M1.run_demo),
    ("2", "M2 - Phân tích Mô hình Giao thông Đô thị (FR-13..17)", M2.run_demo),
    ("3", "M3 - Dự báo Ngắn hạn Naive, ARIMA & Prophet (FR-18..24)", M3.run_demo),
    ("4", "M4 - Dashboard Trực quan hóa & Bảng KPI (FR-25..28, FR-38)", M4.run_demo),
    ("5", "M5 - Quản lý Thực nghiệm & Tái lập Kết quả (FR-29..32)", M5.run_demo),
    ("6", "M6 - Kết xuất Báo cáo CSV/PDF & Nhật ký Audit (FR-33..37)", M6.run_demo),
]


def verify_all_13_tables(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Kiểm thử toàn vẹn và đo tốc độ truy vấn trên toàn bộ 13 bảng của UrbanTrafficAnalyticsDB."""
    tables_spec = [
        ("Phân hệ 1: Người dùng",      "Roles",                    "M0"),
        ("Phân hệ 1: Người dùng",      "Users",                    "M0"),
        ("Phân hệ 1: Người dùng",      "UserRoles",                "M0"),
        ("Phân hệ 2: Quỹ đạo UAV",     "Datasets",                 "M1"),
        ("Phân hệ 2: Quỹ đạo UAV",     "Tracks",                   "M1, M2, M4"),
        ("Phân hệ 2: Quỹ đạo UAV",     "TrajectoryPoints",         "M1, M2, M4"),
        ("Phân hệ 3: Giao thông",      "TrafficSpatialZones",      "M1, M2, M3, M4"),
        ("Phân hệ 3: Giao thông",      "TrafficAggregatedMetrics", "M1, M2, M3, M4, M6"),
        ("Phân hệ 4: Dự báo",          "Experiments",              "M3, M4, M5, M6"),
        ("Phân hệ 4: Dự báo",          "ForecastEvaluations",      "M3, M4, M5, M6"),
        ("Phân hệ 4: Dự báo",          "ForecastResults",          "M3, M4, M5, M6"),
        ("Phân hệ 5: Báo cáo & Audit", "Reports",                  "M6"),
        ("Phân hệ 5: Báo cáo & Audit", "AuditLogs",                "M0, M1, M5, M6"),
    ]
    conn = sqlite3.connect(db_path)
    t0 = time.perf_counter()
    rows = []
    for subsys, tbl, mods in tables_spec:
        cnt = int(conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0])
        rows.append({
            "Phân hệ CSDL": subsys,
            "Tên Bảng (SQL)": tbl,
            "Module sử dụng": mods,
            "Số dòng": cnt,
            "Trạng thái": "✅ Đạt" if cnt > 0 else "❌ Trống",
        })
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    conn.close()

    df = pd.DataFrame(rows)
    print("\n" + "=" * 85)
    print(f"✅ KIỂM THỬ TÍCH HỢP 13 BẢNG TRONG UrbanTrafficAnalyticsDB (Truy vấn: {elapsed_ms:.2f} ms)")
    print("=" * 85)
    print(df.to_string(index=False))
    return df


def run_all_modules() -> None:
    """Thực thi tuần tự toàn bộ 7 module chức năng từ M0 đến M6."""
    t_start = time.perf_counter()
    for _, title, fn in MODULES_REGISTRY:
        print()
        fn()
    verify_all_13_tables(DB_PATH)
    total_sec = time.perf_counter() - t_start
    print(f"\n🎉 ĐÃ CHẠY HOÀN TẤT CẢ 7 MODULE CHỨC NĂNG (M0 -> M6) TRONG {total_sec:.2f} GIÂY!")


def interactive_menu() -> None:
    """Menu tương tác trên Terminal dành cho sinh viên khi trình bày / bảo vệ đồ án."""
    while True:
        print("\n" + "=" * 75)
        print("🚦 HỆ THỐNG PHÂN TÍCH GIAO THÔNG & DỰ BÁO ÙN TẮC UAV (MENU 7 MODULE)")
        print("=" * 75)
        for key, title, _ in MODULES_REGISTRY:
            print(f"  [{key}] {title}")
        print("  [a] Chạy tuần tự toàn bộ 7 Module (M0 -> M6)")
        print("  [c] Kiểm tra nhanh số dòng của 13 bảng trong UrbanTrafficAnalyticsDB")
        print("  [q] Thoát chương trình")
        choice = input("\n👉 Nhập lựa chọn của bạn (0-6 / a / c / q): ").strip().lower()

        if choice == "q":
            print("Đã thoát chương trình.")
            break
        elif choice == "a":
            run_all_modules()
        elif choice == "c":
            verify_all_13_tables(DB_PATH)
        else:
            matched = [fn for k, _, fn in MODULES_REGISTRY if k == choice]
            if matched:
                print()
                matched[0]()
            else:
                print("⚠️ Lựa chọn không hợp lệ, vui lòng nhập lại!")


if __name__ == "__main__":
    if "--menu" in sys.argv:
        interactive_menu()
    else:
        run_all_modules()
