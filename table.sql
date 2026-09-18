-- 1. Create the database
CREATE DATABASE IF NOT EXISTS event_organizer;
USE event_organizer;

-- 2. USERS Table
CREATE TABLE user (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    max_daily_hours DECIMAL(4,2) NOT NULL DEFAULT 6.00,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. EVENTS Table
CREATE TABLE event (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT NULL,
    event_date DATETIME NOT NULL,
    status ENUM('planning', 'in_progress', 'completed', 'cancelled') NOT NULL DEFAULT 'planning',
    progress_percentage DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 4. LOGISTICAL_SUBTASKS Table
CREATE TABLE logistical_subtask (
    subtask_id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT NULL,
    category ENUM('vendors', 'invitations', 'catering', 'venue', 'other') NOT NULL DEFAULT 'other',
    estimated_hours DECIMAL(4,2) NOT NULL,
    scheduled_date DATE NOT NULL,
    status ENUM('pending', 'done', 'postponed') NOT NULL DEFAULT 'pending',
    priority ENUM('low', 'medium', 'high', 'urgent') NOT NULL DEFAULT 'medium',
    FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
);

-- 5. EXECUTION_LOGS Table
CREATE TABLE execution_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    subtask_id INT NOT NULL,
    previous_status VARCHAR(20) NOT NULL,
    new_status ENUM('done', 'postponed') NOT NULL,
    actual_hours DECIMAL(4,2) NULL,
    note TEXT NULL,
    logged_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subtask_id) REFERENCES logistical_subtasks(subtask_id) ON DELETE CASCADE
);

-- 6. CONFLICT_ALERTS Table
CREATE TABLE conflict_alert (
    conflict_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    conflict_date DATE NOT NULL,
    detected_total_hours DECIMAL(4,2) NOT NULL,
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);