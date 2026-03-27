CREATE DATABASE IF NOT EXISTS aiops_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE aiops_db;

CREATE TABLE IF NOT EXISTS `user` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    `email` VARCHAR(100) NOT NULL UNIQUE COMMENT '邮箱',
    `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
    `role_name` VARCHAR(20) NOT NULL DEFAULT 'operator' COMMENT 'operator/superadmin',
    `refresh_token` VARCHAR(512) DEFAULT NULL COMMENT '刷新令牌',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_username` (`username`),
    INDEX `idx_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

CREATE TABLE IF NOT EXISTS `servers` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `hostname` VARCHAR(128) NOT NULL,
    `ip` VARCHAR(64) NOT NULL,
    `port` INT NOT NULL DEFAULT 22,
    `protocol` VARCHAR(32) NOT NULL DEFAULT 'agent',
    `auth_type` VARCHAR(32) DEFAULT 'agent_token',
    `auth_data` TEXT NULL,
    `ssh_username` VARCHAR(128) NULL,
    `ssh_password_ciphertext` TEXT NULL,
    `private_key_ciphertext` TEXT NULL,
    `private_key_passphrase_ciphertext` TEXT NULL,
    `connect_timeout` INT NOT NULL DEFAULT 15,
    `is_enabled` TINYINT(1) NOT NULL DEFAULT 1,
    `agent_token` VARCHAR(128) NULL,
    `status` VARCHAR(32) NOT NULL DEFAULT 'offline',
    `tags` JSON NULL,
    `capabilities` JSON NULL,
    `runtime_stats` JSON NULL,
    `last_seen` DATETIME NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uniq_server_endpoint` (`ip`, `port`),
    INDEX `idx_server_status` (`status`),
    INDEX `idx_server_last_seen` (`last_seen`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='受管服务器信息';

CREATE TABLE IF NOT EXISTS `server_metrics` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `server_id` BIGINT UNSIGNED NOT NULL,
    `cpu_usage` FLOAT DEFAULT 0,
    `memory_usage` FLOAT DEFAULT 0,
    `disk_usage` FLOAT DEFAULT 0,
    `network_rx_mb` FLOAT DEFAULT 0,
    `network_tx_mb` FLOAT DEFAULT 0,
    `metric_payload` JSON NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_metrics_server_id` FOREIGN KEY (`server_id`) REFERENCES `servers` (`id`) ON DELETE CASCADE,
    INDEX `idx_metrics_server_time` (`server_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='服务器监控指标';

CREATE TABLE IF NOT EXISTS `audit_logs` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT UNSIGNED NULL,
    `username` VARCHAR(50) NULL,
    `role_name` VARCHAR(20) NULL,
    `server_id` BIGINT UNSIGNED NULL,
    `session_id` VARCHAR(64) NULL,
    `command_raw` TEXT,
    `command_parsed` TEXT,
    `risk_score` FLOAT DEFAULT 0,
    `risk_level` VARCHAR(16) DEFAULT 'LOW',
    `action` VARCHAR(64),
    `result` VARCHAR(64),
    `detail` TEXT,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_audit_user_time` (`user_id`, `created_at`),
    INDEX `idx_audit_server_time` (`server_id`, `created_at`),
    INDEX `idx_audit_risk` (`risk_level`, `risk_score`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='命令与安全审计日志';

CREATE TABLE IF NOT EXISTS `mfa_challenges` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `session_id` VARCHAR(64) NOT NULL,
    `command_text` TEXT,
    `short_code` VARCHAR(16) NOT NULL,
    `expires_at` DATETIME NOT NULL,
    `used` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_mfa_user_session` (`user_id`, `session_id`),
    INDEX `idx_mfa_expire` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='一次性短码挑战表';

CREATE TABLE IF NOT EXISTS `terminal_sessions` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `session_id` VARCHAR(64) NOT NULL,
    `user_id` BIGINT UNSIGNED NOT NULL,
    `server_id` BIGINT UNSIGNED NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'active',
    `ssh_channel_id` VARCHAR(64) NULL,
    `last_activity` DATETIME NOT NULL,
    `closed_reason` VARCHAR(128) NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uniq_session_id` (`session_id`),
    INDEX `idx_terminal_user` (`user_id`),
    INDEX `idx_terminal_server` (`server_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='终端会话管理';

DROP PROCEDURE IF EXISTS `sp_cleanup_expired_mfa`;
DELIMITER $$
CREATE PROCEDURE `sp_cleanup_expired_mfa`()
BEGIN
    DELETE FROM mfa_challenges
    WHERE used = 1 OR expires_at < NOW() - INTERVAL 1 DAY;
END$$
DELIMITER ;

DROP PROCEDURE IF EXISTS `sp_mark_offline_servers`;
DELIMITER $$
CREATE PROCEDURE `sp_mark_offline_servers`()
BEGIN
    UPDATE servers
    SET status = 'offline', updated_at = NOW()
    WHERE last_seen IS NULL OR last_seen < NOW() - INTERVAL 60 SECOND;
END$$
DELIMITER ;

-- 兼容旧查询名
CREATE OR REPLACE VIEW server_metric AS
SELECT
    id,
    server_id AS user_id,
    CONCAT('server-', server_id) AS server_name,
    cpu_usage,
    memory_usage,
    disk_usage,
    (network_rx_mb + network_tx_mb) AS network_io,
    created_at AS timestamp
FROM server_metrics;

CREATE TABLE IF NOT EXISTS `tenants` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL UNIQUE,
    `status` VARCHAR(20) NOT NULL DEFAULT 'active',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='租户表';

INSERT INTO tenants (id, name, status)
VALUES (1, 'default-tenant', 'active')
ON DUPLICATE KEY UPDATE name=VALUES(name), status=VALUES(status);

ALTER TABLE `user`
    ADD COLUMN IF NOT EXISTS `tenant_id` BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER `role_name`,
    ADD INDEX IF NOT EXISTS `idx_user_tenant` (`tenant_id`);

ALTER TABLE `servers`
    ADD COLUMN IF NOT EXISTS `tenant_id` BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`,
    ADD INDEX IF NOT EXISTS `idx_server_tenant` (`tenant_id`);

ALTER TABLE `audit_logs`
    ADD COLUMN IF NOT EXISTS `trace_id` VARCHAR(64) NULL AFTER `session_id`,
    ADD COLUMN IF NOT EXISTS `incident_id` BIGINT UNSIGNED NULL AFTER `trace_id`;

ALTER TABLE `server_metrics`
    ADD COLUMN IF NOT EXISTS `collector_status` VARCHAR(20) NOT NULL DEFAULT 'ok' AFTER `metric_payload`,
    ADD COLUMN IF NOT EXISTS `collector_error` TEXT NULL AFTER `collector_status`;

DROP TABLE IF EXISTS `runbook_execution_steps`;
DROP TABLE IF EXISTS `runbook_executions`;
DROP TABLE IF EXISTS `runbooks`;

CREATE TABLE IF NOT EXISTS `assistant_approvals` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `tenant_id` BIGINT UNSIGNED NOT NULL,
    `user_id` BIGINT UNSIGNED NULL,
    `suggestion_json` TEXT NOT NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'approved',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_assistant_approval_tenant` (`tenant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数字助手高危建议审批记录';

CREATE TABLE IF NOT EXISTS `backup_jobs` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `tenant_id` BIGINT UNSIGNED NOT NULL,
    `server_id` BIGINT UNSIGNED NOT NULL,
    `backup_type` VARCHAR(32) NOT NULL,
    `target_path` VARCHAR(255) NOT NULL,
    `status` VARCHAR(32) NOT NULL DEFAULT 'pending',
    `result_json` JSON NULL,
    `created_by` BIGINT UNSIGNED NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_backup_tenant_time` (`tenant_id`, `created_at`),
    INDEX `idx_backup_server` (`server_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='备份任务';

CREATE TABLE IF NOT EXISTS `backup_artifacts` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `job_id` BIGINT UNSIGNED NOT NULL,
    `file_path` VARCHAR(255) NOT NULL,
    `file_type` VARCHAR(32) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_backup_artifacts_job` (`job_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='备份产物';

CREATE TABLE IF NOT EXISTS `restore_records` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `tenant_id` BIGINT UNSIGNED NOT NULL,
    `artifact_id` BIGINT UNSIGNED NOT NULL,
    `server_id` BIGINT UNSIGNED NOT NULL,
    `status` VARCHAR(32) NOT NULL DEFAULT 'running',
    `result_json` JSON NULL,
    `created_by` BIGINT UNSIGNED NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_restore_tenant_time` (`tenant_id`, `created_at`),
    INDEX `idx_restore_server` (`server_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='恢复记录';

CREATE TABLE IF NOT EXISTS `batch_jobs` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `tenant_id` BIGINT UNSIGNED NOT NULL,
    `command_text` TEXT NOT NULL,
    `target_server_ids` JSON NOT NULL,
    `status` VARCHAR(32) NOT NULL DEFAULT 'pending_approval',
    `approval_status` VARCHAR(32) NOT NULL DEFAULT 'pending',
    `created_by` BIGINT UNSIGNED NULL,
    `approver_id` BIGINT UNSIGNED NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_batch_tenant_time` (`tenant_id`, `created_at`),
    INDEX `idx_batch_status` (`status`, `approval_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='批量命令任务';

CREATE TABLE IF NOT EXISTS `batch_job_results` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `job_id` BIGINT UNSIGNED NOT NULL,
    `server_id` BIGINT UNSIGNED NOT NULL,
    `status` VARCHAR(32) NOT NULL,
    `result_json` JSON NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_batch_result_job` (`job_id`),
    INDEX `idx_batch_result_server` (`server_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='批量命令执行结果';
