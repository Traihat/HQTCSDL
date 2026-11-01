"""
MODULE 0 (M0): QUẢN LÝ NGƯỜI DÙNG & PHÂN QUYỀN (USER MANAGEMENT & RBAC)
=======================================================================
Đáp ứng yêu cầu chức năng:
  - FR-01: Đăng nhập / kiểm tra xác thực bằng tài khoản và mật khẩu băm SHA-256.
  - FR-02: Phân quyền theo 4 vai trò: Administrator, Researcher, Analyst, Student.
  - FR-03: Cho phép Admin tạo tài khoản, khóa/mở khóa tài khoản và gán vai trò.

Bảng CSDL tương tác (Phân hệ 1 - UrbanTrafficAnalyticsDB):
  - Roles, Users, UserRoles, AuditLogs
"""

import hashlib
import sqlite3
import sys
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Đường dẫn tương đối trỏ tới file CSDL chuẩn của bộ bài nộp 6_nopbai
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "database" / "UrbanTrafficAnalyticsDB.db"

# Ma trận phân quyền chuẩn theo Mục 4 - Tài liệu Yêu cầu chức năng (FR-02)
ROLE_PERMISSIONS = {
    "Administrator": {
        "manage_users",
        "manage_datasets",
        "view_analytics",
        "run_experiments",
        "compare_experiments",
        "export_reports",
        "view_audit_logs",
    },
    "Researcher": {
        "manage_datasets",
        "view_analytics",
        "run_experiments",
        "compare_experiments",
        "export_reports",
    },
    "Analyst": {
        "view_analytics",
        "compare_experiments",
        "export_reports",
    },
    "Student": {
        "view_analytics",
        "compare_experiments",
    },
}


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Mở kết nối SQLite tới UrbanTrafficAnalyticsDB và bật ràng buộc khóa ngoại."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password: str) -> str:
    """Băm mật khẩu một chiều bằng thuật toán SHA-256 (đáp ứng NFR-Security)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_database_if_needed(db_path: Path = DB_PATH) -> None:
    """Khởi tạo 13 bảng CSDL nếu file .db chưa tồn tại (đồng bộ 100% với 01_init_schema.sql)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    schema_sql = """
    CREATE TABLE IF NOT EXISTS Roles (
        role_id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_name TEXT NOT NULL UNIQUE,
        description TEXT
    );
    CREATE TABLE IF NOT EXISTS Users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
    CREATE TABLE IF NOT EXISTS UserRoles (
        user_id INTEGER NOT NULL,
        role_id INTEGER NOT NULL,
        assigned_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (user_id, role_id),
        FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
        FOREIGN KEY (role_id) REFERENCES Roles(role_id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS Datasets (
        dataset_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        source_type TEXT NOT NULL,
        version_tag TEXT NOT NULL,
        location_name TEXT,
        recording_start_time TEXT,
        frame_rate_hz REAL NOT NULL DEFAULT 25.0,
        file_path TEXT,
        status TEXT NOT NULL DEFAULT 'Uploaded',
        uploaded_by INTEGER,
        uploaded_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (uploaded_by) REFERENCES Users(user_id)
    );
    CREATE TABLE IF NOT EXISTS Tracks (
        track_id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_id INTEGER NOT NULL,
        source_track_id INTEGER NOT NULL,
        vehicle_type TEXT NOT NULL,
        total_frames INTEGER NOT NULL DEFAULT 0,
        initial_frame INTEGER,
        final_frame INTEGER,
        FOREIGN KEY (dataset_id) REFERENCES Datasets(dataset_id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS TrajectoryPoints (
        point_id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER NOT NULL,
        frame_id INTEGER NOT NULL,
        timestamp_ms INTEGER NOT NULL,
        x_pos REAL NOT NULL,
        y_pos REAL NOT NULL,
        speed_ms REAL,
        acc_ms2 REAL,
        heading_deg REAL,
        FOREIGN KEY (track_id) REFERENCES Tracks(track_id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS TrafficSpatialZones (
        zone_id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_id INTEGER NOT NULL,
        zone_name TEXT NOT NULL,
        x_min REAL NOT NULL,
        x_max REAL NOT NULL,
        y_min REAL NOT NULL,
        y_max REAL NOT NULL,
        FOREIGN KEY (dataset_id) REFERENCES Datasets(dataset_id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS TrafficAggregatedMetrics (
        metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_id INTEGER NOT NULL,
        zone_id INTEGER,
        window_interval_sec INTEGER NOT NULL,
        window_start_time TEXT NOT NULL,
        window_end_time TEXT NOT NULL,
        vehicle_count INTEGER NOT NULL DEFAULT 0,
        avg_speed_kmh REAL,
        traffic_density_veh_km REAL,
        is_peak_period INTEGER NOT NULL DEFAULT 0,
        congestion_level TEXT,
        FOREIGN KEY (dataset_id) REFERENCES Datasets(dataset_id) ON DELETE CASCADE,
        FOREIGN KEY (zone_id) REFERENCES TrafficSpatialZones(zone_id)
    );
    CREATE TABLE IF NOT EXISTS Experiments (
        experiment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_id INTEGER NOT NULL,
        model_name TEXT NOT NULL,
        aggregation_interval_sec INTEGER NOT NULL,
        hyperparameters TEXT,
        train_ratio REAL NOT NULL DEFAULT 0.80,
        forecast_horizon_min INTEGER NOT NULL DEFAULT 15,
        random_seed INTEGER DEFAULT 42,
        created_by INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (dataset_id) REFERENCES Datasets(dataset_id) ON DELETE CASCADE,
        FOREIGN KEY (created_by) REFERENCES Users(user_id)
    );
    CREATE TABLE IF NOT EXISTS ForecastEvaluations (
        eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id INTEGER NOT NULL UNIQUE,
        mae REAL NOT NULL,
        rmse REAL NOT NULL,
        mape REAL NOT NULL,
        r_squared REAL,
        evaluated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (experiment_id) REFERENCES Experiments(experiment_id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS ForecastResults (
        result_id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id INTEGER NOT NULL,
        forecast_timestamp TEXT NOT NULL,
        actual_value REAL,
        predicted_value REAL NOT NULL,
        lower_bound REAL,
        upper_bound REAL,
        FOREIGN KEY (experiment_id) REFERENCES Experiments(experiment_id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS Reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id INTEGER,
        report_type TEXT NOT NULL,
        file_format TEXT NOT NULL,
        file_path TEXT NOT NULL,
        generated_by INTEGER,
        generated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (experiment_id) REFERENCES Experiments(experiment_id) ON DELETE SET NULL,
        FOREIGN KEY (generated_by) REFERENCES Users(user_id)
    );
    CREATE TABLE IF NOT EXISTS AuditLogs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action_type TEXT NOT NULL,
        entity_name TEXT,
        entity_id TEXT,
        action_details TEXT,
        ip_address TEXT,
        logged_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE SET NULL
    );
    """
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()


def list_users(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Lấy danh sách toàn bộ người dùng kèm vai trò (JOIN 3 bảng Users - UserRoles - Roles)."""
    conn = get_connection(db_path)
    sql = """
    SELECT
        u.user_id,
        u.username,
        u.full_name,
        u.email,
        CASE WHEN u.is_active = 1 THEN 'Active' ELSE 'Locked' END AS trang_thai,
        COALESCE(GROUP_CONCAT(r.role_name, ', '), 'Chưa gán') AS vai_tro,
        u.created_at
    FROM Users u
    LEFT JOIN UserRoles ur ON u.user_id = ur.user_id
    LEFT JOIN Roles r ON ur.role_id = r.role_id
    GROUP BY u.user_id
    ORDER BY u.user_id
    """
    df = pd.read_sql(sql, conn)
    conn.close()
    return df


def login(username: str, password: str, record_audit: bool = False, db_path: Path = DB_PATH) -> dict:
    """
    FR-01: Xác thực đăng nhập người dùng bằng mật khẩu băm SHA-256.
    Trả về dict chứa trạng thái SUCCESS/FAILED, thông tin tài khoản và danh sách quyền.
    """
    pw_hash = hash_password(password)
    conn = get_connection(db_path)
    sql = """
    SELECT u.user_id, u.username, u.full_name, u.email, u.is_active, r.role_name
    FROM Users u
    LEFT JOIN UserRoles ur ON u.user_id = ur.user_id
    LEFT JOIN Roles r ON ur.role_id = r.role_id
    WHERE u.username = ? AND u.password_hash = ?
    """
    df = pd.read_sql(sql, conn, params=(username, pw_hash))

    if df.empty:
        conn.close()
        return {"status": "FAILED", "username": username, "message": "Sai tên đăng nhập hoặc mật khẩu!"}

    if int(df["is_active"].iloc[0]) == 0:
        conn.close()
        return {"status": "LOCKED", "username": username, "message": "Tài khoản đang bị khóa!"}

    roles = [r for r in df["role_name"].dropna().unique().tolist()]
    permissions = sorted({perm for role in roles for perm in ROLE_PERMISSIONS.get(role, set())})
    user_id = int(df["user_id"].iloc[0])

    if record_audit:
        conn.execute(
            """INSERT INTO AuditLogs (user_id, action_type, entity_name, entity_id, action_details, ip_address)
               VALUES (?, 'LOGIN', 'Users', ?, ?, '127.0.0.1')""",
            (user_id, str(user_id), f"Đăng nhập thành công tài khoản '{username}' ({', '.join(roles)})"),
        )
        conn.commit()

    conn.close()
    return {
        "status": "SUCCESS",
        "user_id": user_id,
        "username": username,
        "full_name": str(df["full_name"].iloc[0]),
        "roles": roles,
        "permissions": permissions,
    }


def check_permission(username: str, action: str, db_path: Path = DB_PATH) -> bool:
    """FR-02: Kiểm tra xem người dùng có quyền thực hiện hành động `action` hay không."""
    conn = get_connection(db_path)
    sql = """
    SELECT r.role_name
    FROM Users u
    JOIN UserRoles ur ON u.user_id = ur.user_id
    JOIN Roles r ON ur.role_id = r.role_id
    WHERE u.username = ? AND u.is_active = 1
    """
    df = pd.read_sql(sql, conn, params=(username,))
    conn.close()
    if df.empty:
        return False
    user_perms = {perm for role in df["role_name"].tolist() for perm in ROLE_PERMISSIONS.get(role, set())}
    return action in user_perms


def create_user(
    admin_username: str,
    new_username: str,
    password: str,
    full_name: str,
    email: str,
    role_name: str = "Student",
    db_path: Path = DB_PATH,
) -> dict:
    """FR-03: Cho phép Administrator tạo tài khoản mới và gán vai trò vào bảng UserRoles."""
    if not check_permission(admin_username, "manage_users", db_path):
        return {"status": "DENIED", "message": f"Tài khoản '{admin_username}' không có quyền quản lý người dùng!"}

    conn = get_connection(db_path)
    cur = conn.cursor()
    role_row = cur.execute("SELECT role_id FROM Roles WHERE role_name = ?", (role_name,)).fetchone()
    if not role_row:
        conn.close()
        return {"status": "ERROR", "message": f"Vai trò '{role_name}' không tồn tại trong bảng Roles!"}

    try:
        cur.execute(
            "INSERT INTO Users (username, password_hash, full_name, email, is_active) VALUES (?, ?, ?, ?, 1)",
            (new_username, hash_password(password), full_name, email),
        )
        new_user_id = cur.lastrowid
        cur.execute("INSERT INTO UserRoles (user_id, role_id) VALUES (?, ?)", (new_user_id, role_row[0]))
        conn.commit()
        res = {"status": "SUCCESS", "user_id": new_user_id, "username": new_username, "role": role_name}
    except sqlite3.IntegrityError as exc:
        res = {"status": "ERROR", "message": f"Trùng username hoặc email: {exc}"}
    finally:
        conn.close()
    return res


def set_user_active_status(
    admin_username: str, target_username: str, is_active: bool, db_path: Path = DB_PATH
) -> dict:
    """FR-03: Cho phép Administrator khóa (is_active=0) hoặc mở khóa (is_active=1) tài khoản."""
    if not check_permission(admin_username, "manage_users", db_path):
        return {"status": "DENIED", "message": f"Tài khoản '{admin_username}' không có quyền khóa/mở tài khoản!"}

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE Users SET is_active = ? WHERE username = ?", (1 if is_active else 0, target_username))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    if affected == 0:
        return {"status": "ERROR", "message": f"Không tìm thấy người dùng '{target_username}'."}
    state_label = "Mở khóa (Active)" if is_active else "Khóa (Locked)"
    return {"status": "SUCCESS", "username": target_username, "new_state": state_label}


def assign_role(admin_username: str, target_username: str, role_name: str, db_path: Path = DB_PATH) -> dict:
    """FR-03: Cho phép Administrator thay đổi vai trò của một tài khoản."""
    if not check_permission(admin_username, "manage_users", db_path):
        return {"status": "DENIED", "message": f"Tài khoản '{admin_username}' không có quyền gán vai trò!"}

    conn = get_connection(db_path)
    cur = conn.cursor()
    u_row = cur.execute("SELECT user_id FROM Users WHERE username = ?", (target_username,)).fetchone()
    r_row = cur.execute("SELECT role_id FROM Roles WHERE role_name = ?", (role_name,)).fetchone()
    if not u_row or not r_row:
        conn.close()
        return {"status": "ERROR", "message": "Không tìm thấy người dùng hoặc vai trò tương ứng!"}

    cur.execute("DELETE FROM UserRoles WHERE user_id = ?", (u_row[0],))
    cur.execute("INSERT INTO UserRoles (user_id, role_id) VALUES (?, ?)", (u_row[0], r_row[0]))
    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "username": target_username, "assigned_role": role_name}


def get_permission_matrix_df() -> pd.DataFrame:
    """Tạo bảng đối chiếu ma trận phân quyền RBAC của 4 vai trò để trình bày báo cáo."""
    actions = [
        ("manage_users", "Quản lý người dùng (FR-03)"),
        ("manage_datasets", "Upload, xóa, lưu trữ Dataset (FR-04..09)"),
        ("view_analytics", "Xem Dataset, Phân tích & Dashboard (FR-13..28)"),
        ("run_experiments", "Tạo & chạy thực nghiệm dự báo (FR-19..29)"),
        ("compare_experiments", "So sánh các thực nghiệm (FR-31)"),
        ("export_reports", "Kết xuất báo cáo CSV / PDF (FR-33..36)"),
        ("view_audit_logs", "Tra cứu nhật ký kiểm toán Audit (FR-37)"),
    ]
    rows = []
    for code, desc in actions:
        row = {"Mã quyền": code, "Chức năng nghiệp vụ": desc}
        for role in ["Administrator", "Researcher", "Analyst", "Student"]:
            row[role] = "✔" if code in ROLE_PERMISSIONS[role] else "-"
        rows.append(row)
    return pd.DataFrame(rows)


def run_demo() -> None:
    """Chạy kiểm thử độc lập toàn bộ chức năng của Module 0."""
    print("=" * 85)
    print("🔐 MODULE 0 (M0): QUẢN LÝ NGƯỜI DÙNG & PHÂN QUYỀN (Roles, Users, UserRoles)")
    print("=" * 85)
    init_database_if_needed(DB_PATH)

    print("\n1️⃣ Danh sách tài khoản hiện có trong CSDL UrbanTrafficAnalyticsDB:")
    print(list_users(DB_PATH).to_string(index=False))

    print("\n2️⃣ Ma trận phân quyền RBAC theo 4 vai trò (FR-02):")
    print(get_permission_matrix_df().to_string(index=False))

    print("\n3️⃣ Kiểm thử đăng nhập (FR-01):")
    for uname, pwd in [("admin", "admin123"), ("researcher", "research123"), ("student", "sai_mat_khau")]:
        res = login(uname, pwd, record_audit=False)
        print(f"   • Đăng nhập '{uname}': status={res['status']} -> {res.get('roles', res.get('message'))}")

    print("\n4️⃣ Kiểm thử Admin tạo tài khoản mới, đổi vai trò, khóa tài khoản & dọn dẹp (FR-03):")
    # Dọn trước nếu tài khoản demo tồn tại từ lần chạy dở trước đó
    conn = get_connection(DB_PATH)
    conn.execute("DELETE FROM Users WHERE username = 'sv_demo'")
    conn.commit()
    conn.close()

    print("   • Sinh viên thử tạo user (phải bị chặn):",
          create_user("student", "sv_demo", "123456", "SV Thử Nghiệm", "sv_demo@traffic.edu.vn", "Student"))
    created = create_user("admin", "sv_demo", "123456", "SV Thử Nghiệm", "sv_demo@traffic.edu.vn", "Student")
    print("   • Admin tạo user 'sv_demo':", created)
    print("   • Admin nâng vai trò 'sv_demo' lên Analyst:", assign_role("admin", "sv_demo", "Analyst"))
    print("   • Admin khóa tài khoản 'sv_demo':", set_user_active_status("admin", "sv_demo", False))
    print("   • Đăng nhập 'sv_demo' sau khi bị khóa:", login("sv_demo", "123456"))

    # Xóa user thử nghiệm và reset bộ đếm AUTOINCREMENT để giữ CSDL sạch như ban đầu
    conn = get_connection(DB_PATH)
    conn.execute("DELETE FROM Users WHERE username = 'sv_demo'")
    conn.execute("UPDATE sqlite_sequence SET seq = (SELECT MAX(user_id) FROM Users) WHERE name = 'Users'")
    conn.commit()
    conn.close()
    print("   • Đã dọn tài khoản thử nghiệm 'sv_demo' để bảo toàn dữ liệu chuẩn trong CSDL.")


if __name__ == "__main__":
    run_demo()
