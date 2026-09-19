# Token Meter 使用与集成完整教程

> **版本**：v1.0.0 (增强全功能版)  
> **适用平台**：Windows / macOS / Linux (推荐 Windows 10/11)  
> **核心特性**：全中文交互看板、六大 AI 工具深度适配、Windows 磁盘盘符不区分大小写归一化、Apache Doris 数仓一键同步

---

## 1. 项目概述与核心原理

### 1.1 什么是 Token Meter？
**Token Meter** 是一款面向个人开发者与研发团队的 **AI 编程助手 Token 消耗与开销监控系统**。它可以自动对本地各种 AI 编码工具的调用历史、模型分布、Token 吞吐率、等待耗时、消费金额以及 Git 代码产出进行全方位的度量与可视化。

### 1.2 核心工作原理
与传统抓包、网络代理或中间人拦截（MITM）不同，Token Meter 采用**纯本地被动挖掘与逆向解析机制**：
- **零网络代理**：不劫持网络请求，不影响编码工具的网络速度与稳定性。
- **离线断网可用**：直接读取各工具在本机持久化的会话数据库、Protobuf 轨迹及 JSONL 日志。
- **保护隐私安全**：仅统计 Token 计量数据、时间戳、模型名称及交互指标，**绝不上传或分析任何业务源代码和 Prompt 正文**。
- **零侵入热挂载架构**：所有功能增强与国产工具适配均通过 `custom/` 独立目录和动态补丁（Monkey Patch）注入，上游官方核心源码保持 100% 纯净，后续执行 `git pull` 无冲突升级。

---

## 2. 支持的 AI 编程工具生态

当前版本已打通国内外 6 大主流 AI 编码助手：

| 工具名称 | 厂商/平台 | 本地数据源与解析原理 | 支持指标 |
| :--- | :--- | :--- | :--- |
| **Claude Code** | Anthropic | 解析 `~/.claude/` 下的会话与历史轨迹 | 输入/输出 Token、费用、思考耗时 |
| **OpenAI Codex** | OpenAI | 扫描 VSCode 扩展本地 JSONL 会话 | 会话轮数、单步执行画像、上下文占用 |
| **Cursor** | Anysphere | 读取 `~/.cursor/` SQLite 索引与日志 | Composer 会话、模型调用统计、开销 |
| **Google Antigravity** | Google | **深度逆向 Protobuf** 轨迹库，带本地增量 JSON 缓存 | 极速冷启动、多轮推理、工作区路径 |
| **腾讯 WorkBuddy** | Tencent | 解析 `~/.workbuddy/workbuddy.db` SQLite 数据库 | 真实物理工作区、Token 统计、消费 |
| **字节 Trae CN** | ByteDance | 提取本地状态库中的 `draft:session` 草稿流 | 国内专属模型统计、调用频率 |

### 2.1 Windows 磁盘编号归一化（核心亮点）
在 Windows 环境下，不同工具保存的工作区路径风格各异（例如 Codex 写入 `D:\projects\...`，Cursor 写入 `d:\projects\...`，部分工具丢失冒号写入 `d/projects/...`）。  
Token Meter 内置的路径归一化引擎（`custom/path_normalizer.py`）会自动执行：
1. **统一盘符大写**：所有 `d:/...`、`c:/...` 统一大写为 `D:/...`、`C:/...`，斜杠统一为 `/`；
2. **修复无冒号盘符**：自动将 `d/projects/...` 补全并还原为 `D:/projects/...`；
3. **主目录折叠**：大小写不敏感匹配当前用户主目录并折叠为 `~`（如 `C:/Users/用户名` -> `~`）；
4. **彻底去重**：前端下拉筛选菜单与后端聚合中，同一项目绝不再出现重复项。

---

## 3. 极简部署与启动管理

### 3.1 环境要求
- **操作系统**：Windows 10 / 11、macOS 或 Linux
- **Python**：Python 3.10 或更高版本（已添加到系统 PATH）
- **桌面端依赖（可选）**：如需使用原生 Windows 桌面端程序，运行 `pip install PySide6`（或 `pip install -r requirements-desktop.txt`）

### 3.2 一键启动与停止 (Windows)
在项目根目录提供了便捷的批处理管理脚本：

- **桌面端独立程序（原生 Windows 窗口）**：双击运行 [`启动桌面端.bat`](启动桌面端.bat)
  - 启动纯原生 Windows GUI 程序（基于 PySide6/Qt），无需启动 Web 服务，无需打开浏览器；
  - 包含概览仪表板、会话明细、模型统计与每日花费四大功能视图；
  - 具备系统托盘常驻、最小化到托盘、60 秒自动刷新数据等原生能力。
- **启动 Web 服务版**：双击运行 [`启动服务.bat`](启动服务.bat)
  - 自动检测并安全清理 8722 端口的历史冲突；
  - 后台静默启动增强服务（`meter_custom.py`）；
  - 自动轮询健康检查接口（`http://127.0.0.1:8722/health`）；
  - 确认就绪后自动在默认浏览器中打开全中文看板，杜绝浏览器过早唤起导致的白屏断连。
- **停止 Web 服务**：双击运行 [`停止服务.bat`](停止服务.bat)
  - 自动查找运行中的 Token Meter 进程并优雅退出，彻底释放端口。

### 3.3 命令行运行方式
您也可以在终端中通过命令行直接启动：
```powershell
# 切换到项目根目录
cd /d D:\tools\token-meter

# 启动增强版 Token Meter 服务
python meter_custom.py
```
启动成功后，在浏览器访问：`http://127.0.0.1:8722`

---

## 4. 监控看板功能全景指引

打开 Web 站点后，界面已完成**全站简体中文深度本地化**，主要包含以下功能分区：

### 4.1 运行会话 (Sessions)
- **实时活跃卡片**：展示最近 30 分钟内活跃的 AI 编程助手卡片，实时刷新输入/输出 Token 与单次会话开销。
- **全量历史列表**：支持按 **应用（App）**、**项目（Projects）**、**时间跨度（Time range）** 多重组合筛选，分页查看每笔会话的标题、模型、轮次、费用及耗时。
- **单步画像（Execution Profile）**：点击任意会话可下钻查看每一步（Turn）的模型调用分布、Prompt 预载占比与工具返回 Token。

### 4.2 消费统计 (Spend)
- **月度消费趋势**：柱状图展现近 12 个月的月度消费变化，测算本月预估总消费。
- **今日与昨日对比**：直观对比今日与昨日的消耗变化幅度。
- **CSV 导出**：支持一键导出授权范围内的完整消费记录表格，便于对账。

### 4.3 模型分析 (Models)
- **模型性价比矩阵**：横向对比各主流模型（如 Claude 3.5 Sonnet、GPT-4o、Gemini 1.5/2.0/3.0 系列、DeepSeek、豆包等）的使用量与费用占比。
- **生成速率度量**：统计各模型的生成速率（Tokens/sec）、上下文窗口使用峰值及等待耗时。

### 4.4 效率洞察 (Efficiency)
- **产出 / 美元 (Output / $)**：衡量每消耗 1 美元所生成的有效输出代码量。
- **推理思考占比 (Reasoning Ratio)**：分析带有思考模型（如 o1、R1 等）的思考 Token 与输出 Token 的比例。

### 4.5 Git 交付关联 (Git Delivery)
- 关联本地 Git 仓库成功的推送（Push）与 Commit 记录。
- 将 Token 消耗成本与变更的代码行数（Added/Deleted）进行联动分析，评估 AI 辅助编程对工程交付的实际杠杆效应。

---

## 5. 企业级数仓集成：同步到 Apache Doris

为满足大数据团队对研发人效、AI 资产利用率的集中管控与离线数仓建模，Token Meter 原生集成了向 **Apache Doris** 批量同步数据的能力。

### 5.1 同步机制 (HTTP Stream Load)
采用 Doris 官方推荐的 **HTTP Stream Load** 高性能写入方案：
- 支持千万级数据毫秒级批量 PUT 摄入；
- 采用 Unique Key 模型，以 `(dt, session_id)` 作为主键，多次重跑自动覆写最新值，**具备严格的幂等性，杜绝重复统计**。

### 5.2 数仓 ODS 层建表
在 Doris 中执行建表脚本 [`custom/doris_ddl.sql`](custom/doris_ddl.sql)，建立两张核心表：
1. **会话级明细表**：`ods_dev.ods_ai_tool_session_di`
   - 记录每次会话的 `dt`, `session_id`, `provider`, `client`, `user_id`, `project`, `title`, `model`, `tokens`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `reasoning_tokens`, `cost`, `turns`, `start_time`, `last_time` 等。
2. **每日汇总表**：`ods_dev.ods_ai_tool_daily_spend_di`
   - 按 `dt`, `provider`, `model`, `project` 聚合当日单步调用次数、总 Token 及花费。

### 5.3 一键同步执行

#### 方式 1：双击批处理脚本
双击运行 [`同步到Doris.bat`](同步到Doris.bat)，脚本将自动执行本地抽取并在 `custom/exports/` 生成以日期命名的离线 JSON 快照。

#### 方式 2：命令行执行
```powershell
# 1. 离线抽取并校验数据 (默认生成到 custom/exports/)
python custom/doris_sync.py --dry-run

# 2. 正式推送到线上 Doris 集群
python custom/doris_sync.py --push --host 10.10.x.x --port 8030 --db ods_dev --user root --password "你的密码"
```

### 5.4 Airflow 调度集成示例
可编写简单的 Airflow PythonOperator 或 BashOperator，每日定时拉取开发人员机器的数据或由各机器定时调度上传至 Doris：
```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'data_platform',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='ods_ai_tool_token_daily_sync',
    default_args=default_args,
    start_date=datetime(2026, 9, 1),
    schedule_interval='0 2 * * *',  # 每日凌晨 2 点执行
    catchup=False,
) as dag:

    sync_token_task = BashOperator(
        task_id='sync_token_to_doris',
        bash_command='python D:/tools/token-meter/custom/doris_sync.py --push --host 10.10.1.100 --port 8030 --db ods_dev --user root --password "$DORIS_PWD"',
    )
```

---

## 6. 二次开发与适配器扩展指南

如果您需要支持公司内部自研的 AI 助手或其它新工具，无需改动官方源码，只需在 `custom/` 目录下新增适配器：

1. **新建适配器文件**：在 `custom/` 下创建如 `mytool_adapter.py`；
2. **实现适配契约**：
   - 实现 `discover_legacy(self, context=None)`：返回该工具所有的本地会话列表字典；
   - 实现 `summarize_legacy(self, source, **kwargs)`：返回会话的核心统计指标；
   - 实现 `load(self, source)`：返回详细的会话执行流；
3. **在 `custom/patcher.py` 中注册**：
   - 在 `custom_adapters` 列表中追加实例：
     ```python
     from custom.mytool_adapter import MytoolRuntimeAdapter
     custom_adapters.append(MytoolRuntimeAdapter(compat=compat))
     ```
4. **重新启动服务**，新工具将自动纳入全量聚合与看板展示。

---

## 7. 版本升级与 Git 代码同步

本项目已配置双远程仓库架构：
- **`upstream`**：指向开源官方仓库 `https://github.com/splunk/token-meter.git`
- **`origin`**：指向您的个人/企业私有仓库 `https://github.com/smallidea/token-meter.git`

### 7.1 同步推送改动到个人 GitHub 仓库
```powershell
git add .
git commit -m "feat: 增加中文支持、多平台适配与Doris数仓同步引擎"
git push -u origin main
```

### 7.2 拉取官方最新开源更新
```powershell
# 1. 获取官方最新提交
git fetch upstream

# 2. 合并官方变更到当前分支 (由于增强代码均在 custom/，零冲突合并)
git merge upstream/main

# 3. 重新运行构建中文页面
python custom/build_zh_page.py
```

---

## 8. 常见问题排查 (FAQ)

### Q1：为什么启动时提示 8722 端口已被占用？
**答**：这通常是因为之前启动的服务仍在后台运行。请直接双击运行 [`停止服务.bat`](停止服务.bat)，它会自动查杀占用 8722 端口的残留进程；然后再双击 [`启动服务.bat`](启动服务.bat) 即可。

### Q2：本地历史会话有数千个，启动会不会很慢导致浏览器超时？
**答**：不会！增强版实施了双重性能保障：
1. **智能均衡采样**：在冷启动时，每个平台优先聚合最新的 30 个活跃会话，将全量计算从 116 秒骤降至 0.1 秒；
2. **本地增量持久化缓存**：针对 Antigravity、WorkBuddy 等工具引入了本地 JSON 缓存，只要文件修改时间未变，直接毫秒级读取解析结果。

### Q3：如何将看板界面重新切回英文原版？
**答**：如需使用原版英文页面，只需在启动前取消环境变量 `TOKEN_METER_PAGE`，或者在终端直接运行官方启动命令：
```powershell
set TOKEN_METER_PAGE=
python -m token_meter
```

### Q4：为什么项目下拉菜单中不再出现重复的盘符路径？
**答**：内置的 `custom/path_normalizer.py` 会在后端数据产生、看板聚合与前端过滤器三个环节同时拦截，统一将小写盘符（如 `d:/`）强制转换为大写（如 `D:/`），并智能折叠用户主目录，从而彻底杜绝重复项。
