CREATE DATABASE IF NOT EXISTS stock_db;
USE stock_db;

CREATE TABLE IF NOT EXISTS live_stock_prices (
    symbol VARCHAR(10),
    price DECIMAL(10,2),
    timestamp DATETIME
);

CREATE TABLE IF NOT EXISTS stock_prices (
    symbol VARCHAR(10),
    price DECIMAL(10,2),
    timestamp DATETIME
);

CREATE TABLE IF NOT EXISTS sma_20d (
    symbol VARCHAR(10) PRIMARY KEY,
    sma DECIMAL(10,4)
);
