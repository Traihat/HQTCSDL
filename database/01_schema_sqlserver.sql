-- ==========================================================================================
-- KỊCH BẢN KHỞI TẠO CƠ SỞ DỮ LIỆU SQL SERVER: UrbanTrafficDynamicDB (9 BẢNG - KHÔNG PHÂN QUYỀN)
-- Thiết kế mới hoàn toàn cho 6 Module trong `1_nhu_cau_khach_hang.md`:
--   1. DatasetImports        : Quản lý phiên nạp file .xlsx / .xls / .csv (Tối đa 3 GB)
--   2. DynamicZones          : Danh mục Khu vực đô thị chia tự động từ dữ liệu nạp vào
--   3. DynamicTimeFrames     : Danh mục Khung giờ chia tự động từ thời gian thực tế trong file
--   4. CleanedTrajectories   : Dữ liệu quỹ đạo phương tiện UAV sau 4 bước tiền xử lý
--   5. TrafficPatternMetrics : Chỉ số giao thông tổng hợp, giờ cao điểm & điểm nóng ùn tắc
--   6. ForecastComparisons   : Kết quả đánh giá & câu nhận xét so sánh ARIMA vs Prophet
--   7. ForecastPoints        : Chuỗi điểm dự báo ARIMA & Prophet (Ngày gốc, Ngày +1, Ngày +2 & Khung giờ)
--   8. ExperimentRuns        : Quản lý cấu hình thực nghiệm, siêu tham số & tái lập (Module 5)
--   9. GeneratedReports      : Quản lý báo cáo phân tích, dự báo, hiệu năng & xuất PDF/Excel (Module 6)
-- ==========================================================================================

IF DB_ID('UrbanTrafficDynamicDB') IS NULL
    CREATE DATABASE UrbanTrafficDynamicDB;
GO

USE UrbanTrafficDynamicDB;
GO

IF EXISTS (
    SELECT 1
    FROM sys.tables
    WHERE name IN (
        'DatasetImports', 'DynamicZones', 'DynamicTimeFrames', 'CleanedTrajectories',
        'TrafficPatternMetrics', 'ForecastComparisons', 'ForecastPoints',
        'ExperimentRuns', 'GeneratedReports'
    )
)
    THROW 51000, 'Existing UrbanTrafficDynamicDB tables detected. This bootstrap script is for a new database only; back up and use an additive migration instead.', 1;
GO

IF OBJECT_ID('dbo.sp_ClearAllDatabaseData', 'P') IS NOT NULL DROP PROCEDURE dbo.sp_ClearAllDatabaseData;
IF OBJECT_ID('dbo.GeneratedReports', 'U') IS NOT NULL DROP TABLE dbo.GeneratedReports;
IF OBJECT_ID('dbo.ExperimentRuns', 'U') IS NOT NULL DROP TABLE dbo.ExperimentRuns;
IF OBJECT_ID('dbo.ForecastPoints', 'U') IS NOT NULL DROP TABLE dbo.ForecastPoints;
IF OBJECT_ID('dbo.ForecastComparisons', 'U') IS NOT NULL DROP TABLE dbo.ForecastComparisons;
IF OBJECT_ID('dbo.TrafficPatternMetrics', 'U') IS NOT NULL DROP TABLE dbo.TrafficPatternMetrics;
IF OBJECT_ID('dbo.CleanedTrajectories', 'U') IS NOT NULL DROP TABLE dbo.CleanedTrajectories;
IF OBJECT_ID('dbo.DynamicTimeFrames', 'U') IS NOT NULL DROP TABLE dbo.DynamicTimeFrames;
IF OBJECT_ID('dbo.DynamicZones', 'U') IS NOT NULL DROP TABLE dbo.DynamicZones;
IF OBJECT_ID('dbo.DatasetImports', 'U') IS NOT NULL DROP TABLE dbo.DatasetImports;
GO

-- 1. Bảng DatasetImports (Module 1)
CREATE TABLE dbo.DatasetImports (
    import_id               INT IDENTITY(1,1) PRIMARY KEY,
    file_name               NVARCHAR(255) NOT NULL,
    file_extension          VARCHAR(15)   NOT NULL CHECK (file_extension IN ('.xlsx', '.xls', '.csv')),
    file_size_kb            FLOAT         NOT NULL CHECK (file_size_kb >= 0 AND file_size_kb <= 3145728),
    raw_row_count           INT           NOT NULL CHECK (raw_row_count >= 0),
    cleaned_row_count       INT           NOT NULL CHECK (cleaned_row_count >= 0),
    removed_missing_dup     INT           NOT NULL DEFAULT 0,
    removed_stationary      INT           NOT NULL DEFAULT 0,
    removed_outliers        INT           NOT NULL DEFAULT 0,
    dynamic_zone_count      INT           NOT NULL DEFAULT 0,
    dynamic_timeframe_count INT           NOT NULL DEFAULT 0,
    time_range_start        VARCHAR(30)   NULL,
    time_range_end          VARCHAR(30)   NULL,
    status_message          NVARCHAR(500) NOT NULL,
    imported_at             DATETIME2     NOT NULL DEFAULT SYSDATETIME()
);

-- 2. Bảng DynamicZones (Module 1, 2, 3, 4, 5, 6)
CREATE TABLE dbo.DynamicZones (
    zone_id                 INT IDENTITY(1,1) PRIMARY KEY,
    import_id               INT           NOT NULL,
    zone_code               VARCHAR(50)   NOT NULL,
    zone_name               NVARCHAR(150) NOT NULL,
    partition_method        NVARCHAR(80)  NOT NULL,
    x_min_m                 FLOAT         NOT NULL,
    x_max_m                 FLOAT         NOT NULL,
    y_min_m                 FLOAT         NOT NULL,
    y_max_m                 FLOAT         NOT NULL,
    road_length_km          FLOAT         NOT NULL CHECK (road_length_km > 0),
    CONSTRAINT FK_DynamicZones_Import FOREIGN KEY (import_id) REFERENCES dbo.DatasetImports(import_id) ON DELETE CASCADE
);

-- 3. Bảng DynamicTimeFrames (Module 1, 2, 3, 4, 6)
CREATE TABLE dbo.DynamicTimeFrames (
    timeframe_id            INT IDENTITY(1,1) PRIMARY KEY,
    import_id               INT           NOT NULL,
    timeframe_code          VARCHAR(50)   NOT NULL,
    timeframe_label         NVARCHAR(120) NOT NULL,
    start_time_str          VARCHAR(30)   NOT NULL,
    end_time_str            VARCHAR(30)   NOT NULL,
    start_epoch_sec         FLOAT         NOT NULL,
    end_epoch_sec           FLOAT         NOT NULL,
    duration_minutes        FLOAT         NOT NULL CHECK (duration_minutes > 0),
    is_peak_timeframe       BIT           NOT NULL DEFAULT 0,
    CONSTRAINT FK_DynamicTimeFrames_Import FOREIGN KEY (import_id) REFERENCES dbo.DatasetImports(import_id) ON DELETE CASCADE
);

-- 4. Bảng CleanedTrajectories (Module 1, 2, 4)
CREATE TABLE dbo.CleanedTrajectories (
    trajectory_id           BIGINT IDENTITY(1,1) PRIMARY KEY,
    import_id               INT           NOT NULL,
    zone_id                 INT           NOT NULL,
    timeframe_id            INT           NOT NULL,
    vehicle_id              VARCHAR(60)   NOT NULL,
    vehicle_type            NVARCHAR(50)  NOT NULL,
    recorded_time_str       VARCHAR(30)   NOT NULL,
    time_sec                FLOAT         NOT NULL,
    x_coord_m               FLOAT         NOT NULL,
    y_coord_m               FLOAT         NOT NULL,
    speed_kmh               FLOAT         NOT NULL CHECK (speed_kmh >= 0 AND speed_kmh <= 150),
    accel_ms2               FLOAT         NOT NULL CHECK (accel_ms2 >= -15 AND accel_ms2 <= 15),
    lane_no                 INT           NOT NULL DEFAULT 1,
    CONSTRAINT FK_Traj_Import FOREIGN KEY (import_id) REFERENCES dbo.DatasetImports(import_id) ON DELETE CASCADE,
    CONSTRAINT FK_Traj_Zone   FOREIGN KEY (zone_id) REFERENCES dbo.DynamicZones(zone_id),
    CONSTRAINT FK_Traj_TF     FOREIGN KEY (timeframe_id) REFERENCES dbo.DynamicTimeFrames(timeframe_id)
);

-- 5. Bảng TrafficPatternMetrics (Module 2, 3, 4, 6)
CREATE TABLE dbo.TrafficPatternMetrics (
    metric_id               INT IDENTITY(1,1) PRIMARY KEY,
    import_id               INT           NOT NULL,
    zone_id                 INT           NOT NULL,
    timeframe_id            INT           NOT NULL,
    window_index            INT           NOT NULL,
    window_time_label       VARCHAR(30)   NOT NULL,
    window_duration_sec     INT           NOT NULL CHECK (window_duration_sec > 0),
    vehicle_count           INT           NOT NULL CHECK (vehicle_count >= 0),
    car_count               INT           NOT NULL DEFAULT 0,
    motorbike_count         INT           NOT NULL DEFAULT 0,
    bus_truck_count         INT           NOT NULL DEFAULT 0,
    avg_speed_kmh           FLOAT         NOT NULL CHECK (avg_speed_kmh >= 0),
    traffic_density_veh_km  FLOAT         NOT NULL CHECK (traffic_density_veh_km >= 0),
    traffic_flow_veh_h      FLOAT         NOT NULL CHECK (traffic_flow_veh_h >= 0),
    slow_vehicle_ratio_pct  FLOAT         NOT NULL DEFAULT 0,
    is_peak_hour            BIT           NOT NULL DEFAULT 0,
    is_hotspot              BIT           NOT NULL DEFAULT 0,
    hotspot_location        NVARCHAR(255) NULL,
    hotspot_score           FLOAT         NOT NULL DEFAULT 0,
    congestion_level        VARCHAR(30)   NOT NULL CHECK (congestion_level IN ('Free Flow', 'Moderate', 'Heavy', 'Gridlock')),
    CONSTRAINT FK_Metrics_Import FOREIGN KEY (import_id) REFERENCES dbo.DatasetImports(import_id) ON DELETE CASCADE,
    CONSTRAINT FK_Metrics_Zone   FOREIGN KEY (zone_id) REFERENCES dbo.DynamicZones(zone_id),
    CONSTRAINT FK_Metrics_TF     FOREIGN KEY (timeframe_id) REFERENCES dbo.DynamicTimeFrames(timeframe_id)
);

-- 6. Bảng ForecastComparisons (Module 3, 4, 6)
CREATE TABLE dbo.ForecastComparisons (
    comparison_id           INT IDENTITY(1,1) PRIMARY KEY,
    import_id               INT           NOT NULL,
    zone_id                 INT           NOT NULL,
    arima_order_str         VARCHAR(60)   NOT NULL,
    arima_mae               FLOAT         NOT NULL,
    arima_rmse              FLOAT         NOT NULL,
    arima_mape_pct          FLOAT         NOT NULL,
    arima_r2                FLOAT         NOT NULL,
    prophet_seasonality_str VARCHAR(100)  NOT NULL,
    prophet_mae             FLOAT         NOT NULL,
    prophet_rmse            FLOAT         NOT NULL,
    prophet_mape_pct        FLOAT         NOT NULL,
    prophet_r2              FLOAT         NOT NULL,
    better_model            VARCHAR(20)   NOT NULL CHECK (better_model IN ('ARIMA', 'Prophet')),
    rmse_improvement_pct    FLOAT         NOT NULL,
    commentary_text         NVARCHAR(1200) NOT NULL,
    created_at              DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT FK_ForecastComp_Import FOREIGN KEY (import_id) REFERENCES dbo.DatasetImports(import_id) ON DELETE CASCADE,
    CONSTRAINT FK_ForecastComp_Zone   FOREIGN KEY (zone_id) REFERENCES dbo.DynamicZones(zone_id)
);

-- 7. Bảng ForecastPoints (Module 3, 4, 6 — Hỗ trợ Filter Dự báo 2 Ngày sau đó & Filter Khung giờ)
CREATE TABLE dbo.ForecastPoints (
    point_id                INT IDENTITY(1,1) PRIMARY KEY,
    comparison_id           INT           NOT NULL,
    timeframe_id            INT           NULL,
    day_offset              INT           NOT NULL DEFAULT 0 CHECK (day_offset IN (0, 1, 2)),
    forecast_date_label     NVARCHAR(60)  NOT NULL DEFAULT N'Ngày gốc (Day 0)',
    step_index              INT           NOT NULL,
    time_label              VARCHAR(40)   NOT NULL,
    phase_type              VARCHAR(20)   NOT NULL CHECK (phase_type IN ('Train', 'Test', 'Future_Day1', 'Future_Day2')),
    actual_density          FLOAT         NULL,
    arima_predicted         FLOAT         NOT NULL,
    arima_lower_95          FLOAT         NOT NULL,
    arima_upper_95          FLOAT         NOT NULL,
    prophet_predicted       FLOAT         NOT NULL,
    prophet_lower_95        FLOAT         NOT NULL,
    prophet_upper_95        FLOAT         NOT NULL,
    CONSTRAINT FK_ForecastPoints_Comp FOREIGN KEY (comparison_id) REFERENCES dbo.ForecastComparisons(comparison_id) ON DELETE CASCADE
);

-- 8. Bảng ExperimentRuns (Module 5: Experiment Management & Reproducibility)
CREATE TABLE dbo.ExperimentRuns (
    experiment_id             INT IDENTITY(1,1) PRIMARY KEY,
    import_id                 INT           NOT NULL,
    zone_id                   INT           NOT NULL,
    experiment_code           VARCHAR(40)   NOT NULL,
    experiment_name           NVARCHAR(200) NOT NULL,
    temporal_interval_sec     INT           NOT NULL CHECK (temporal_interval_sec > 0),
    train_ratio               FLOAT         NOT NULL CHECK (train_ratio >= 0.5 AND train_ratio <= 0.95),
    arima_order_str           VARCHAR(40)   NOT NULL,
    prophet_fourier_k         INT           NOT NULL DEFAULT 3,
    prophet_changepoint_scale FLOAT         NOT NULL DEFAULT 0.15,
    random_seed               INT           NOT NULL DEFAULT 42,
    dataset_version           VARCHAR(30)   NOT NULL DEFAULT 'v1.0',
    software_version          VARCHAR(40)   NOT NULL DEFAULT 'UTA-Platform v2.0',
    arima_mae                 FLOAT         NOT NULL,
    arima_rmse                FLOAT         NOT NULL,
    arima_mape_pct            FLOAT         NOT NULL,
    arima_r2                  FLOAT         NOT NULL,
    prophet_mae               FLOAT         NOT NULL,
    prophet_rmse              FLOAT         NOT NULL,
    prophet_mape_pct          FLOAT         NOT NULL,
    prophet_r2                FLOAT         NOT NULL,
    winner_model              VARCHAR(20)   NOT NULL CHECK (winner_model IN ('ARIMA', 'Prophet')),
    execution_time_ms         FLOAT         NOT NULL,
    reproducibility_hash      VARCHAR(64)   NOT NULL,
    notes                     NVARCHAR(500) NULL,
    created_at                DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT FK_Experiment_Import FOREIGN KEY (import_id) REFERENCES dbo.DatasetImports(import_id) ON DELETE CASCADE,
    CONSTRAINT FK_Experiment_Zone   FOREIGN KEY (zone_id) REFERENCES dbo.DynamicZones(zone_id)
);

-- 9. Bảng GeneratedReports (Module 6: Reporting & PDF/Excel Export)
CREATE TABLE dbo.GeneratedReports (
    report_id                 INT IDENTITY(1,1) PRIMARY KEY,
    import_id                 INT           NOT NULL,
    report_code               VARCHAR(40)   NOT NULL,
    report_title              NVARCHAR(250) NOT NULL,
    report_type               VARCHAR(50)   NOT NULL CHECK (report_type IN ('Traffic_Analysis', 'Forecast_2Days', 'Performance_Experiment', 'Comprehensive_Full')),
    export_format             VARCHAR(20)   NOT NULL CHECK (export_format IN ('PDF', 'EXCEL', 'WEB_PREVIEW')),
    zone_scope                NVARCHAR(150) NOT NULL,
    horizon_scope             NVARCHAR(100) NOT NULL,
    summary_highlights        NVARCHAR(1000) NOT NULL,
    generated_at              DATETIME2     NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT FK_Report_Import FOREIGN KEY (import_id) REFERENCES dbo.DatasetImports(import_id) ON DELETE CASCADE
);
GO

-- Stored Procedure hỗ trợ nút Xóa Database & Dữ liệu cũ ở Module 1 an toàn 100% trên SQL Server
CREATE PROCEDURE dbo.sp_ClearAllDatabaseData
AS
BEGIN
    SET NOCOUNT ON;
    DELETE FROM dbo.GeneratedReports;
    DELETE FROM dbo.ExperimentRuns;
    DELETE FROM dbo.ForecastPoints;
    DELETE FROM dbo.ForecastComparisons;
    DELETE FROM dbo.TrafficPatternMetrics;
    DELETE FROM dbo.CleanedTrajectories;
    DELETE FROM dbo.DynamicTimeFrames;
    DELETE FROM dbo.DynamicZones;
    DELETE FROM dbo.DatasetImports;
    SELECT N'Da xoa thanh cong database va du lieu cu. San sang de nhan du lieu moi' AS StatusMessage;
END;
GO

