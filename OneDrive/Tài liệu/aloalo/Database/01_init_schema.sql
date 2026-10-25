-- ========================================================
-- 0. TẠO CƠ SỞ DỮ LIỆU
-- ========================================================
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'UrbanTrafficAnalyticsDB')
BEGIN
    CREATE DATABASE UrbanTrafficAnalyticsDB;
END
GO

USE UrbanTrafficAnalyticsDB;
GO

-- ========================================================
-- PHÂN HỆ 1: PHÂN QUYỀN & NGƯỜI DÙNG (User Management)
-- ========================================================

-- Bảng Roles: Quản lý các vai trò (Administrator, Researcher, Analyst, Student)
CREATE TABLE Roles (
    role_id INT IDENTITY(1,1) PRIMARY KEY,
    role_name NVARCHAR(50) NOT NULL UNIQUE,
    description NVARCHAR(255) NULL
);
GO

-- Bảng Users: Quản lý thông tin tài khoản
CREATE TABLE Users (
    user_id INT IDENTITY(1,1) PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    full_name NVARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    is_active BIT NOT NULL DEFAULT 1,
    created_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME()
);
GO

-- Bảng UserRoles: Quan hệ nhiều - nhiều giữa Users và Roles
CREATE TABLE UserRoles (
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    assigned_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT PK_UserRoles PRIMARY KEY CLUSTERED (user_id, role_id),
    CONSTRAINT FK_UserRoles_Users FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
    CONSTRAINT FK_UserRoles_Roles FOREIGN KEY (role_id) REFERENCES Roles(role_id) ON DELETE CASCADE
);
GO

-- ========================================================
-- PHÂN HỆ 2: QUẢN LÝ TẬP DỮ LIỆU & QUỸ ĐẠO UAV (Datasets & Trajectories)
-- ========================================================

-- Bảng Datasets: Quản lý phiên bản và metadata của các file inD / pNEUMA
CREATE TABLE Datasets (
    dataset_id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(150) NOT NULL,
    source_type VARCHAR(50) NOT NULL,          -- 'inD', 'pNEUMA', etc.
    version_tag VARCHAR(20) NOT NULL,          -- 'v1.0', 'v2.1'
    location_name NVARCHAR(100) NOT NULL,      -- 'Heckstrasse Intersection', etc.
    recording_start_time DATETIME2(3) NULL,
    frame_rate_hz DECIMAL(5,2) NOT NULL DEFAULT 25.00,
    file_path NVARCHAR(500) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Uploaded', -- 'Uploaded', 'Validating', 'Ready', 'Archived'
    uploaded_by INT NOT NULL,
    created_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT FK_Datasets_Users FOREIGN KEY (uploaded_by) REFERENCES Users(user_id)
);
GO

-- Bảng Tracks: Quản lý từng đối tượng phương tiện được theo dõi trong dataset
CREATE TABLE Tracks (
    track_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    dataset_id INT NOT NULL,
    source_track_id INT NOT NULL,              -- ID gốc từ file CSV của UAV
    vehicle_type VARCHAR(30) NOT NULL,         -- 'car', 'truck', 'bus', 'pedestrian', 'motorcycle'
    total_frames INT NOT NULL,
    initial_frame INT NOT NULL,
    final_frame INT NOT NULL,
    CONSTRAINT FK_Tracks_Datasets FOREIGN KEY (dataset_id) REFERENCES Datasets(dataset_id) ON DELETE CASCADE,
    CONSTRAINT UQ_Tracks_Dataset_SourceTrack UNIQUE (dataset_id, source_track_id)
);
GO

-- Bảng TrajectoryPoints: Dữ liệu tọa độ chi tiết từng frame (Dữ liệu lớn nhất)
-- Dùng Composite Clustered Index trên (track_id, frame_id) để tối ưu việc đọc hành trình liên tục
CREATE TABLE TrajectoryPoints (
    point_id BIGINT IDENTITY(1,1) NOT NULL,
    track_id BIGINT NOT NULL,
    frame_id INT NOT NULL,
    timestamp_ms BIGINT NOT NULL,              -- Thời gian trôi qua tính từ lúc bắt đầu (ms)
    x_pos DECIMAL(9,3) NOT NULL,               -- Tọa độ X (mét)
    y_pos DECIMAL(9,3) NOT NULL,               -- Tọa độ Y (mét)
    speed_ms DECIMAL(6,2) NOT NULL,            -- Vận tốc (m/s)
    acc_ms2 DECIMAL(6,2) NULL,                 -- Gia tốc (m/s²)
    heading_deg DECIMAL(5,2) NULL,             -- Hướng di chuyển (độ)
    CONSTRAINT PK_TrajectoryPoints PRIMARY KEY NONCLUSTERED (point_id),
    CONSTRAINT FK_TrajectoryPoints_Tracks FOREIGN KEY (track_id) REFERENCES Tracks(track_id) ON DELETE CASCADE
);
GO

-- Clustered Index tổ chức dữ liệu vật lý theo track và frame
CREATE CLUSTERED INDEX CIX_TrajectoryPoints_Track_Frame 
ON TrajectoryPoints (track_id, frame_id);
GO

-- ========================================================
-- PHÂN HỆ 3: TỔNG HỢP MÔ HÌNH GIAO THÔNG (Traffic Aggregation & Patterns)
-- ========================================================

-- Bảng TrafficSpatialZones: Chia khu vực ngã tư thành các zone nhỏ để bắt hotspot
CREATE TABLE TrafficSpatialZones (
    zone_id INT IDENTITY(1,1) PRIMARY KEY,
    dataset_id INT NOT NULL,
    zone_name VARCHAR(50) NOT NULL,
    x_min DECIMAL(9,3) NOT NULL,
    x_max DECIMAL(9,3) NOT NULL,
    y_min DECIMAL(9,3) NOT NULL,
    y_max DECIMAL(9,3) NOT NULL,
    CONSTRAINT FK_Zones_Datasets FOREIGN KEY (dataset_id) REFERENCES Datasets(dataset_id) ON DELETE CASCADE
);
GO

-- Bảng TrafficAggregatedMetrics: Dữ liệu chuỗi thời gian gom nhóm (Time-Series Table)
-- Lưu kết quả sau khi aggregate theo từng bước thời gian (1, 5, 15 phút) để cấp cho AI/Dashboard
CREATE TABLE TrafficAggregatedMetrics (
    metric_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    dataset_id INT NOT NULL,
    zone_id INT NULL,                          -- NULL nếu là metric tính chung toàn khu vực
    window_interval_sec INT NOT NULL,          -- 60 (1m), 300 (5m), 900 (15m)
    window_start_time DATETIME2(0) NOT NULL,
    window_end_time DATETIME2(0) NOT NULL,
    vehicle_count INT NOT NULL DEFAULT 0,
    avg_speed_kmh DECIMAL(5,2) NOT NULL DEFAULT 0.0,
    traffic_density_veh_km DECIMAL(6,2) NOT NULL DEFAULT 0.0,
    is_peak_period BIT NOT NULL DEFAULT 0,
    congestion_level VARCHAR(20) NOT NULL DEFAULT 'Free Flow', -- 'Free Flow', 'Moderate', 'Heavy', 'Gridlock'
    CONSTRAINT FK_AggMetrics_Datasets FOREIGN KEY (dataset_id) REFERENCES Datasets(dataset_id) ON DELETE CASCADE,
    CONSTRAINT FK_AggMetrics_Zones FOREIGN KEY (zone_id) REFERENCES TrafficSpatialZones(zone_id)
);
GO

-- ========================================================
-- PHÂN HỆ 4: QUẢN LÝ THỰC NGHIỆM & DỰ BÁO (Experiments & Forecasting)
-- ========================================================

-- Bảng Experiments: Quản lý cấu hình huấn luyện mô hình (ARIMA / Prophet)
CREATE TABLE Experiments (
    experiment_id INT IDENTITY(1,1) PRIMARY KEY,
    dataset_id INT NOT NULL,
    model_name VARCHAR(50) NOT NULL,           -- 'ARIMA', 'Prophet'
    aggregation_interval_sec INT NOT NULL,     -- Chu kỳ gộp dữ liệu đầu vào (ví dụ: 900s)
    hyperparameters NVARCHAR(MAX) NOT NULL,     -- Lưu JSON: {"p":1, "d":1, "q":1} hoặc changepoint_prior_scale
    train_ratio DECIMAL(3,2) NOT NULL DEFAULT 0.80,
    forecast_horizon_min INT NOT NULL,         -- Số phút dự báo tới: 15, 30, 60
    random_seed INT NULL,
    created_by INT NOT NULL,
    created_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT FK_Experiments_Datasets FOREIGN KEY (dataset_id) REFERENCES Datasets(dataset_id),
    CONSTRAINT FK_Experiments_Users FOREIGN KEY (created_by) REFERENCES Users(user_id)
);
GO

-- Bảng ForecastEvaluations: Lưu các chỉ số đánh giá độ chính xác (Metrics)
CREATE TABLE ForecastEvaluations (
    eval_id INT IDENTITY(1,1) PRIMARY KEY,
    experiment_id INT NOT NULL UNIQUE,
    mae DECIMAL(8,4) NOT NULL,
    rmse DECIMAL(8,4) NOT NULL,
    mape DECIMAL(6,2) NOT NULL,
    r_squared DECIMAL(5,4) NOT NULL,
    evaluated_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT FK_Evaluations_Experiments FOREIGN KEY (experiment_id) REFERENCES Experiments(experiment_id) ON DELETE CASCADE
);
GO

-- Bảng ForecastResults: Giá trị dự báo chi tiết theo thời gian thực tế vs dự báo
CREATE TABLE ForecastResults (
    result_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    experiment_id INT NOT NULL,
    forecast_timestamp DATETIME2(0) NOT NULL,
    actual_value DECIMAL(8,2) NULL,
    predicted_value DECIMAL(8,2) NOT NULL,
    lower_bound DECIMAL(8,2) NULL,             -- Cận dưới khoảng tin cậy (Confidence Interval)
    upper_bound DECIMAL(8,2) NULL,             -- Cận trên khoảng tin cậy
    CONSTRAINT FK_ForecastResults_Experiments FOREIGN KEY (experiment_id) REFERENCES Experiments(experiment_id) ON DELETE CASCADE
);
GO

-- ========================================================
-- PHÂN HỆ 5: BÁO CÁO & NHẬT KÝ KIỂM TOÁN (Reporting & Audit Log)
-- ========================================================

-- Bảng Reports: Quản lý các file báo cáo PDF / Excel đã sinh ra
CREATE TABLE Reports (
    report_id INT IDENTITY(1,1) PRIMARY KEY,
    experiment_id INT NULL,
    report_type VARCHAR(30) NOT NULL,          -- 'TrafficPattern', 'ForecastComparison', 'ExecutiveSummary'
    file_format VARCHAR(10) NOT NULL,          -- 'PDF', 'XLSX'
    file_path NVARCHAR(500) NOT NULL,
    generated_by INT NOT NULL,
    generated_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT FK_Reports_Experiments FOREIGN KEY (experiment_id) REFERENCES Experiments(experiment_id) ON DELETE SET NULL,
    CONSTRAINT FK_Reports_Users FOREIGN KEY (generated_by) REFERENCES Users(user_id)
);
GO

-- Bảng AuditLogs: Ghi vết toàn bộ hành động người dùng theo FR Audit Trail
CREATE TABLE AuditLogs (
    log_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NULL,
    action_type VARCHAR(50) NOT NULL,          -- 'UPLOAD_DATASET', 'RUN_EXPERIMENT', 'EXPORT_REPORT'
    entity_name VARCHAR(50) NOT NULL,          -- 'Datasets', 'Experiments', 'Reports'
    entity_id VARCHAR(50) NULL,
    action_details NVARCHAR(MAX) NULL,
    ip_address VARCHAR(45) NULL,
    logged_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT FK_AuditLogs_Users FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE SET NULL
);
GO

-- ========================================================
-- PHÂN HỆ 6: NON-CLUSTERED INDEXES (Tối ưu hóa hiệu năng truy vấn)
-- ========================================================

-- Tăng tốc độ truy vấn danh sách quỹ đạo theo tập dữ liệu và loại xe
CREATE NONCLUSTERED INDEX IX_Tracks_Dataset_VehicleType 
ON Tracks (dataset_id, vehicle_type) 
INCLUDE (source_track_id, total_frames);
GO

-- Tăng tốc độ lọc chuỗi thời gian vẽ biểu đồ theo khung thời gian
CREATE NONCLUSTERED INDEX IX_AggMetrics_Dataset_Interval_Time 
ON TrafficAggregatedMetrics (dataset_id, window_interval_sec, window_start_time)
INCLUDE (vehicle_count, avg_speed_kmh, traffic_density_veh_km, congestion_level);
GO

-- Tăng tốc độ vẽ đường dự báo vs thực tế trên dashboard
CREATE NONCLUSTERED INDEX IX_ForecastResults_Experiment_Timestamp 
ON ForecastResults (experiment_id, forecast_timestamp)
INCLUDE (actual_value, predicted_value, lower_bound, upper_bound);
GO

-- Tăng tốc độ tra cứu lịch sử hành động người dùng
CREATE NONCLUSTERED INDEX IX_AuditLogs_User_LoggedAt 
ON AuditLogs (user_id, logged_at DESC);
GO