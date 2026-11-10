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

