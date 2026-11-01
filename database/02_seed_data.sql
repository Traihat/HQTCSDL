-- ========================================================
-- FILE: 02_seed_data.sql
-- Mục đích: Khởi tạo dữ liệu mẫu ban đầu cho UrbanTrafficAnalyticsDB
-- ========================================================
USE UrbanTrafficAnalyticsDB;
GO

-- 1. Thêm 4 vai trò chuẩn theo đề cương (FR1: User Management)
INSERT INTO Roles (role_name, description) VALUES
(N'Administrator', N'Quản trị hệ thống, quản lý người dùng và xem nhật ký Audit'),
(N'Researcher',    N'Nhà nghiên cứu: tải dữ liệu UAV, tạo và chạy mô hình dự báo'),
(N'Analyst',       N'Chuyên viên phân tích: xem thống kê giao thông, điểm nóng và xuất báo cáo'),
(N'Student',       N'Sinh viên: xem dữ liệu, biểu đồ dashboard và kết quả thực nghiệm');
GO

-- 2. Thêm các tài khoản người dùng mẫu
INSERT INTO Users (username, password_hash, full_name, email, is_active) VALUES
('admin',      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', N'Quản Trị Viên',      'admin@traffic.edu.vn', 1),
('researcher', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', N'Nguyễn Văn Nghiên',  'researcher@traffic.edu.vn', 1),
('analyst',    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', N'Trần Thị Phân Tích', 'analyst@traffic.edu.vn', 1),
('student',    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', N'Sinh Viên Năm 3',    'student@traffic.edu.vn', 1);
GO

-- 3. Gán vai trò cho người dùng
INSERT INTO UserRoles (user_id, role_id) VALUES
(1, 1), -- admin -> Administrator
(2, 2), -- researcher -> Researcher
(3, 3), -- analyst -> Analyst
(4, 4); -- student -> Student
GO

-- 4. Thêm thông tin Dataset UAV mẫu
INSERT INTO Datasets (name, source_type, version_tag, location_name, recording_start_time, frame_rate_hz, file_path, status, uploaded_by)
VALUES
(N'UAV_ListDB_DorKoh_Session1', 'ListDB_UAV', 'v1.0', N'Nút giao DorKoh (TU Dresden)', '2022-06-02 10:00:00', 10.00, N'data/raw/listdb_sample.csv', 'Ready', 2),
(N'UAV_inD_Benchmark',          'inD',        'v1.0', N'Heckstrasse Intersection',     '2019-05-15 08:00:00', 25.00, N'data/raw/ind_sample.csv',    'Uploaded', 2);
GO

-- 5. Ghi nhận Audit Log ban đầu
INSERT INTO AuditLogs (user_id, action_type, entity_name, entity_id, action_details, ip_address)
VALUES
(1, 'INIT_SYSTEM',    'Database', '1', N'Khởi tạo CSDL UrbanTrafficAnalyticsDB và tài khoản mặc định', '127.0.0.1'),
(2, 'UPLOAD_DATASET', 'Datasets', '1', N'Tải lên tập dữ liệu quỹ đạo UAV_ListDB_DorKoh_Session1 (v1.0)', '127.0.0.1');
GO
