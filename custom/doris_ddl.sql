-- =============================================================================
-- Token Meter -> Apache Doris ODS 层建表 DDL
-- 适用环境: Apache Doris 1.2+ / 2.0+
-- 数仓分层: ODS (原始操作数据层)
-- =============================================================================

CREATE DATABASE IF NOT EXISTS ods_dev;
USE ods_dev;

-- -----------------------------------------------------------------------------
-- 1. AI 编程助手会话级明细表 (Unique Key 模型，支持 Stream Load 自动幂等去重)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ods_dev.ods_ai_tool_session_di (
    `dt` DATE NOT NULL COMMENT "统计日期 (按会话活跃日期)",
    `session_id` VARCHAR(128) NOT NULL COMMENT "会话全局唯一ID",
    `provider` VARCHAR(32) NOT NULL DEFAULT "" COMMENT "工具供应商 (antigravity/codex/cursor/workbuddy/traecn/claude)",
    `client` VARCHAR(32) DEFAULT "" COMMENT "客户端类型",
    `user_id` VARCHAR(64) DEFAULT "" COMMENT "员工工号或系统识别ID",
    `user_name` VARCHAR(64) DEFAULT "" COMMENT "员工姓名",
    `project` VARCHAR(256) DEFAULT "" COMMENT "归一化后的项目路径 (统一 Windows 大写盘符)",
    `title` VARCHAR(256) DEFAULT "" COMMENT "会话标题",
    `model` VARCHAR(64) DEFAULT "" COMMENT "主力调用模型",
    `model_provider` VARCHAR(32) DEFAULT "" COMMENT "模型供应商 (openai/anthropic/google/tencent/bytedance)",
    `tokens` BIGINT DEFAULT "0" COMMENT "总消耗 Token 数量",
    `input_tokens` BIGINT DEFAULT "0" COMMENT "输入 Token 数量",
    `output_tokens` BIGINT DEFAULT "0" COMMENT "输出 Token 数量",
    `cache_read_tokens` BIGINT DEFAULT "0" COMMENT "缓存读取 Token 数量",
    `reasoning_tokens` BIGINT DEFAULT "0" COMMENT "思考推理 Token 数量",
    `cost` DECIMAL(10, 6) DEFAULT "0.000000" COMMENT "模型开销金额 (USD)",
    `turns` INT DEFAULT "0" COMMENT "交互会话轮数",
    `start_time` DATETIME COMMENT "会话开始时间",
    `last_time` DATETIME COMMENT "会话最后活跃时间",
    `source_path` VARCHAR(512) DEFAULT "" COMMENT "本地会话数据存储路径",
    `sync_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT "数仓抽取入库时间"
)
UNIQUE KEY(`dt`, `session_id`)
PARTITION BY RANGE(`dt`) ()
DISTRIBUTED BY HASH(`session_id`) BUCKETS 10
PROPERTIES (
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-90",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "10",
    "replication_num" = "3",
    "enable_unique_key_merge_on_write" = "true"
);

-- -----------------------------------------------------------------------------
-- 2. AI 编程助手每日消费聚合表
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ods_dev.ods_ai_tool_daily_spend_di (
    `dt` DATE NOT NULL COMMENT "统计日期",
    `provider` VARCHAR(32) NOT NULL DEFAULT "" COMMENT "工具供应商",
    `model` VARCHAR(64) NOT NULL DEFAULT "" COMMENT "模型名称",
    `project` VARCHAR(256) NOT NULL DEFAULT "" COMMENT "项目标识",
    `user_id` VARCHAR(64) DEFAULT "" COMMENT "员工工号",
    `executions` INT DEFAULT "0" COMMENT "当日单步调用/执行次数",
    `tokens` BIGINT DEFAULT "0" COMMENT "当日总消耗 Token 数量",
    `input_tokens` BIGINT DEFAULT "0" COMMENT "当日输入 Token 数量",
    `output_tokens` BIGINT DEFAULT "0" COMMENT "当日输出 Token 数量",
    `cost` DECIMAL(10, 6) DEFAULT "0.000000" COMMENT "当日模型开销金额 (USD)",
    `sync_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT "数仓抽取入库时间"
)
UNIQUE KEY(`dt`, `provider`, `model`, `project`)
PARTITION BY RANGE(`dt`) ()
DISTRIBUTED BY HASH(`provider`, `model`) BUCKETS 5
PROPERTIES (
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-90",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "5",
    "replication_num" = "3",
    "enable_unique_key_merge_on_write" = "true"
);
