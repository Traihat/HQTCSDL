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

-- Nạp dữ liệu khởi tạo mẫu vào cả 9 bảng để kiểm tra trực tiếp trên SQL Server
INSERT INTO dbo.DatasetImports (
    file_name, file_extension, file_size_kb, raw_row_count, cleaned_row_count,
    removed_missing_dup, removed_stationary, removed_outliers,
    dynamic_zone_count, dynamic_timeframe_count, time_range_start, time_range_end, status_message
) VALUES (
    N'UAV_Urban_Traffic_Dataset.csv', '.csv', 245.8, 4210, 4065,
    45, 62, 38, 4, 4, '2026-11-06 07:00:00', '2026-11-06 09:00:00',
    N'Đã xử lý dữ liệu và đưa dữ liệu vào database thành công!'
);

DECLARE @imp_id INT = SCOPE_IDENTITY();

INSERT INTO dbo.DynamicZones (import_id, zone_code, zone_name, partition_method, x_min_m, x_max_m, y_min_m, y_max_m, road_length_km)
VALUES
    (@imp_id, 'DYN_ZONE_1', N'Nút Giao Trung Tâm (Central Hub)', N'Extracted_From_File_Columns', 220, 480, 300, 620, 1.35),
    (@imp_id, 'DYN_ZONE_2', N'Đại Lộ Hướng Bắc (North Corridor)', N'Extracted_From_File_Columns', 500, 880, 640, 980, 1.65),
    (@imp_id, 'DYN_ZONE_3', N'Trục Thương Mại Đông (East Avenue)', N'Extracted_From_File_Columns', 900, 1280, 320, 720, 1.45),
    (@imp_id, 'DYN_ZONE_4', N'Cầu Vượt Cửa Ngõ Nam (South Overpass)', N'Extracted_From_File_Columns', 260, 760, 80, 290, 1.80);

INSERT INTO dbo.DynamicTimeFrames (import_id, timeframe_code, timeframe_label, start_time_str, end_time_str, start_epoch_sec, end_epoch_sec, duration_minutes, is_peak_timeframe)
VALUES
    (@imp_id, 'TF_1', N'07:00 - 07:30', '2026-11-06 07:00:00', '2026-11-06 07:30:00', 0, 1800, 30, 0),
    (@imp_id, 'TF_2', N'07:30 - 08:00 (Cao điểm)', '2026-11-06 07:30:00', '2026-11-06 08:00:00', 1800, 3600, 30, 1),
    (@imp_id, 'TF_3', N'08:00 - 08:30 (Cao điểm)', '2026-11-06 08:00:00', '2026-11-06 08:30:00', 3600, 5400, 30, 1),
    (@imp_id, 'TF_4', N'08:30 - 09:00', '2026-11-06 08:30:00', '2026-11-06 09:00:00', 5400, 7200, 30, 0);

DECLARE @z1 INT = (SELECT TOP 1 zone_id FROM dbo.DynamicZones WHERE import_id = @imp_id ORDER BY zone_id);
DECLARE @tf1 INT = (SELECT TOP 1 timeframe_id FROM dbo.DynamicTimeFrames WHERE import_id = @imp_id ORDER BY timeframe_id);

INSERT INTO dbo.CleanedTrajectories (import_id, zone_id, timeframe_id, vehicle_id, vehicle_type, recorded_time_str, time_sec, x_coord_m, y_coord_m, speed_kmh, accel_ms2, lane_no)
VALUES
    (@imp_id, @z1, @tf1, 'UAV_1001', N'Car', '2026-11-06 07:05:00', 300, 310.5, 420.2, 26.4, 0.25, 1),
    (@imp_id, @z1, @tf1, 'UAV_1002', N'Motorbike', '2026-11-06 07:10:00', 600, 345.0, 460.8, 22.1, -0.15, 2);

INSERT INTO dbo.TrafficPatternMetrics (
    import_id, zone_id, timeframe_id, window_index, window_time_label, window_duration_sec,
    vehicle_count, car_count, motorbike_count, bus_truck_count,
    avg_speed_kmh, traffic_density_veh_km, traffic_flow_veh_h, slow_vehicle_ratio_pct,
    is_peak_hour, is_hotspot, hotspot_location, hotspot_score, congestion_level
) VALUES
    (@imp_id, @z1, @tf1, 1, '07:00', 300, 42, 20, 16, 6, 24.5, 31.1, 761.9, 18.5, 1, 1, N'Nút Giao Trung Tâm - Làn 1', 1.24, 'Moderate');

INSERT INTO dbo.ForecastComparisons (
    import_id, zone_id, arima_order_str, arima_mae, arima_rmse, arima_mape_pct, arima_r2,
    prophet_seasonality_str, prophet_mae, prophet_rmse, prophet_mape_pct, prophet_r2,
    better_model, rmse_improvement_pct, commentary_text
) VALUES (
    @imp_id, @z1, 'ARIMA(1,1,1)', 1.65, 2.04, 5.8, 0.88,
    'Prophet(Fourier K=3, P=9.5)', 1.32, 1.68, 4.7, 0.92,
    'Prophet', 17.65, N'Nhận xét: Mô hình Prophet đạt độ chính xác cao hơn ARIMA nhờ hàm chu kỳ điều hòa Fourier.'
);

DECLARE @comp_id INT = SCOPE_IDENTITY();

INSERT INTO dbo.ForecastPoints (
    comparison_id, timeframe_id, day_offset, forecast_date_label, step_index, time_label,
    phase_type, actual_density, arima_predicted, arima_lower_95, arima_upper_95,
    prophet_predicted, prophet_lower_95, prophet_upper_95
) VALUES
    (@comp_id, @tf1, 0, N'Ngày Hiện Tại (Day 0)', 1, '07:00', 'Train', 31.1, 30.8, 28.5, 33.1, 31.0, 29.0, 33.0),
    (@comp_id, @tf1, 1, N'Dự báo Ngày +1 (+24h)', 2, 'Ngày +1 07:00', 'Future_Day1', 32.5, 32.1, 29.1, 35.1, 32.4, 29.8, 35.0),
    (@comp_id, @tf1, 2, N'Dự báo Ngày +2 (+48h)', 3, 'Ngày +2 07:00', 'Future_Day2', 33.6, 33.0, 29.5, 36.5, 33.5, 30.5, 36.5);

INSERT INTO dbo.ExperimentRuns (
    import_id, zone_id, experiment_code, experiment_name, temporal_interval_sec, train_ratio,
    arima_order_str, prophet_fourier_k, prophet_changepoint_scale, random_seed, dataset_version,
    software_version, arima_mae, arima_rmse, arima_mape_pct, arima_r2,
    prophet_mae, prophet_rmse, prophet_mape_pct, prophet_r2,
    winner_model, execution_time_ms, reproducibility_hash, notes
) VALUES (
    @imp_id, @z1, 'EXP-01-Z1', N'Baseline 60s — ARIMA(1,1,0) vs Prophet(K=2)', 60, 0.75,
    'ARIMA(1,1,0)', 2, 0.15, 42, 'v1.0-UAV', 'UTA-Platform v2.0',
    1.65, 2.04, 5.8, 0.88, 1.32, 1.68, 4.7, 0.92,
    'Prophet', 24.5, 'SHA256-8F4A2C91E0B3', N'Cấu hình cơ sở 60 giây'
);

INSERT INTO dbo.GeneratedReports (
    import_id, report_code, report_title, report_type, export_format,
    zone_scope, horizon_scope, summary_highlights
) VALUES (
    @imp_id, 'RPT-01-FULL', N'Báo Cáo Tổng Hợp Toàn Hệ Thống 6 Module', 'Comprehensive_Full', 'PDF',
    N'Tất cả 4 Khu vực động', N'Ngày gốc (Day 0) + Dự báo 2 Ngày sau đó (+48h)',
    N'Tổng hợp phân tích mẫu hình giao thông, dự báo đa ngày và thực nghiệm tái lập.'
);
GO

-- Hiển thị bảng kiểm tra 9 bảng sau khi khởi tạo
SELECT 1 AS STT, 'DatasetImports' AS TableName, COUNT(*) AS TotalRows FROM dbo.DatasetImports
UNION ALL SELECT 2, 'DynamicZones', COUNT(*) FROM dbo.DynamicZones
UNION ALL SELECT 3, 'DynamicTimeFrames', COUNT(*) FROM dbo.DynamicTimeFrames
UNION ALL SELECT 4, 'CleanedTrajectories', COUNT(*) FROM dbo.CleanedTrajectories
UNION ALL SELECT 5, 'TrafficPatternMetrics', COUNT(*) FROM dbo.TrafficPatternMetrics
UNION ALL SELECT 6, 'ForecastComparisons', COUNT(*) FROM dbo.ForecastComparisons
UNION ALL SELECT 7, 'ForecastPoints', COUNT(*) FROM dbo.ForecastPoints
UNION ALL SELECT 8, 'ExperimentRuns', COUNT(*) FROM dbo.ExperimentRuns
UNION ALL SELECT 9, 'GeneratedReports', COUNT(*) FROM dbo.GeneratedReports;
GO
