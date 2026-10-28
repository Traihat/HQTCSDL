
USE master;
GO

IF DB_ID(N'UrbanTrafficAnalytics') IS NULL
BEGIN
    CREATE DATABASE UrbanTrafficAnalytics;
END;
GO

USE UrbanTrafficAnalytics;
GO
