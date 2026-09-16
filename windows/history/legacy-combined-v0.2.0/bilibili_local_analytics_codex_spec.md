# B站公开视频数据本地采集与分析工具开发文档

> 交付对象：Codex / 本地开发助手  
> 目标平台：Windows 11 本地电脑  
> 后续扩展：安卓 / 鸿蒙只作为局域网查看端或控制端  
> 项目性质：公开视频数据的本地采集、存储、分析与报告生成  
> 明确限制：不购买服务器、不使用云数据库、不绕过验证码、不使用代理池、不抓取私密/付费/会员限制内容、不默认开放局域网访问

---

## 0. 项目定位

开发一个运行在用户本地 Windows 电脑上的 B站公开视频数据采集与分析工具。

工具允许用户输入 B站视频链接或 BV 号，程序在本地定时采集该视频的公开互动数据，并生成可视化图表报告。

第一版不开发安卓 App、不开发鸿蒙 App，也不开放局域网访问。Windows 程序只启动本机 Web 服务，默认仅监听 `127.0.0.1`，用户只能在本机浏览器查看和控制。

手机端局域网访问属于后续阶段功能，只有在加入访问密码、明确风险提示和手动开关后才允许实现。

---

## 1. 核心原则

### 1.1 本地优先

所有数据、配置、报告、日志均存储在本机。

不得依赖：

- 云服务器
- 云数据库
- 第三方代理池
- 远程任务调度服务
- 付费 API

### 1.2 合规与安全边界

程序必须遵守以下限制：

1. 优先使用 B站官方开放平台或官方允许的接口能力；如果使用网页公开接口，只能作为个人本地学习和观察用途，并明确存在平台规则、接口变化和服务条款风险。
2. 只采集公开视频的公开可访问统计数据，不应把“公开视频”理解为“平台允许任意自动化采集”。
3. 不采集私信、未公开视频、付费内容、会员限制内容、账号后台数据。
4. 不绕过登录、验证码、风控、反爬机制。
5. 不实现代理池、IP 轮换、设备指纹伪造、App 签名模拟等功能。
6. 不进行秒级高频抓取。
7. Cookie 如需使用，只允许用户手动提供，并且必须本地加密保存。
8. 默认不要求登录。
9. 所有网络请求必须有频率限制、超时设置、失败退避和日志记录。
10. 当平台返回 403、412、验证码、风控、接口变更或异常结构时，程序必须停止当前任务或进入冷却，不得自动寻找替代接口、不得尝试绕过。

### 1.3 第一版范围控制

第一版只完成：

- 单视频 / 多视频的基础互动数据采集
- 本地 SQLite 存储
- 本机 Web 控制面板，仅监听 `127.0.0.1`
- 基础趋势图表
- HTML 报告导出
- 基础测试用例

第一版暂不实现：

- 安卓原生 App
- 鸿蒙原生 App
- 自动登录
- 多账号管理
- 评论全文深度抓取
- 弹幕全文深度抓取
- AI 情绪分析
- 大规模批量视频采集
- 高频实时监控
- 手机局域网访问
- exe 打包发布

---

## 2. 推荐技术栈

### 2.1 后端与采集

- Python 3.11+
- httpx：网络请求
- APScheduler：定时任务
- SQLite：本地数据库
- SQLAlchemy：数据库 ORM，可选
- Pydantic：数据校验
- Loguru 或 logging：日志

### 2.2 本地 Web 面板

优先级：

1. FastAPI + Jinja2 + Plotly：结构清楚，适合任务控制、报告页面和后续维护。
2. NiceGUI：开发最快，适合快速原型，但长期维护、打包和页面结构控制需要额外评估。
3. Streamlit：适合快速数据展示，但任务控制体验较弱，不建议作为第一版主方案。

建议第一版使用：

```text
FastAPI + Jinja2 + SQLite + httpx + APScheduler + Plotly
```

如果开发目标是尽快做出可操作原型，可以改用 NiceGUI，但必须保持采集、调度、数据库、报告服务与 UI 解耦，避免业务逻辑写死在页面事件里。

### 2.3 图表与报告

- Plotly：交互式图表
- Jinja2：HTML 报告模板
- Pandas：数据分析
- Markdown 导出：可选
- PDF 导出：后续版本再做

### 2.4 打包

- PyInstaller

### 2.5 数据源与接口策略

第一版必须先明确数据源，再实现采集逻辑。不得让 Codex 在实现过程中临时搜索、拼凑或替换接口。

数据源优先级：

1. 优先评估 B站官方开放平台或官方文档允许的接口能力。
2. 如果官方开放平台不能满足个人本地观察所需字段，才允许使用公开视频页面可公开访问的统计接口作为实验性数据源。
3. 使用网页公开接口时，README 和报告说明中必须写明：接口可能变化、数据可能不稳定、使用者需自行遵守平台规则。

必须提供 `DataProvider` 抽象，避免采集逻辑与具体 URL 强绑定：

```python
class VideoDataProvider:
    async def fetch_video_info(self, bvid: str) -> VideoInfo:
        ...

    async def fetch_video_stats(self, bvid: str) -> VideoStats:
        ...
```

实现前必须在代码或测试夹具中保留至少一份脱敏示例响应，用于字段映射和 mock 测试。

接口异常处理原则：

- `code != 0` 时不得当作成功数据保存。
- 403、412、验证码、风控提示、登录要求、响应结构明显变化时，当前任务进入冷却或错误状态。
- 不得自动尝试备用接口、不得模拟客户端、不得绕过风控。
- 字段缺失时可以保存 `None`，但必须记录日志并在页面提示数据不完整。

---

## 3. 总体架构

```text
bilibili-local-analytics/
├─ app/
│  ├─ main.py                    # 程序入口
│  ├─ config.py                  # 配置读取与默认参数
│  ├─ database.py                # 数据库连接与初始化
│  ├─ models.py                  # 数据库模型
│  ├─ scheduler.py               # 定时任务管理
│  ├─ logger.py                  # 日志配置
│  │
│  ├─ collectors/
│  │  ├─ __init__.py
│  │  ├─ bilibili_client.py      # B站请求客户端
│  │  ├─ provider.py             # 数据源抽象与字段映射
│  │  ├─ video_info.py           # 视频基础信息采集
│  │  ├─ stats.py                # 互动数据快照采集
│  │  ├─ comments.py             # 第二阶段占位：评论采集，不在第一版启用
│  │  └─ danmaku.py              # 第二阶段占位：弹幕采集，不在第一版启用
│  │
│  ├─ services/
│  │  ├─ video_service.py        # 视频任务管理
│  │  ├─ task_service.py         # 采集任务状态管理
│  │  ├─ crawl_service.py        # 采集流程编排
│  │  ├─ report_service.py       # 报告生成
│  │  └─ analysis_service.py     # 数据分析
│  │
│  ├─ ui/
│  │  ├─ dashboard.py            # Web 面板
│  │  ├─ pages.py                # 页面路由
│  │  └─ components.py           # UI 组件
│  │
│  ├─ reports/
│  │  ├─ templates/
│  │  │  └─ report.html.j2       # HTML 报告模板
│  │
│  └─ tests/
│     ├─ test_bvid_parser.py
│     ├─ test_database.py
│     ├─ test_rate_limit.py
│     └─ test_report.py
│
├─ data/
│  ├─ bilibili_local.db           # SQLite 数据库
│  └─ exports/                    # CSV / HTML 导出
│
├─ reports/
│  └─ output/                      # HTML 报告输出目录
│
├─ logs/
│  └─ app.log
│
├─ requirements.txt
├─ README.md
└─ run.bat
```

---

## 4. 第一版功能需求

## 4.1 输入视频

用户可以输入：

- BV 号，例如：`BV1xx411c7mD`
- B站视频链接，例如：`https://www.bilibili.com/video/BVxxxx`

程序需要解析出 BV 号。

### 4.1.1 BV 号解析要求

实现函数：

```python
def parse_bvid(text: str) -> str:
    """从 BV 号或 B站视频链接中解析出 BV 号。"""
```

要求：

1. 能识别纯 BV 号。
2. 能识别包含查询参数的链接。
3. 输入非法时抛出明确异常。
4. 不要静默失败。

示例：

```text
BV1xx411c7mD -> BV1xx411c7mD
https://www.bilibili.com/video/BV1xx411c7mD/ -> BV1xx411c7mD
https://www.bilibili.com/video/BV1xx411c7mD/?spm_id_from=xxx -> BV1xx411c7mD
```

---

## 4.2 添加采集任务

用户在 Web 面板中输入 BV 号后，程序需要：

1. 解析 BV 号。
2. 请求公开视频基础信息。
3. 保存到 `videos` 表。
4. 保存或更新 `crawl_tasks` 表中的采集任务。
5. 在任务列表中显示该视频。

如果视频不可访问：

- 显示错误提示。
- 写入日志。
- 不创建任务。

---

## 4.3 定时采集视频互动数据

第一版采集字段：

- 播放量 view
- 弹幕数 danmaku
- 评论数 reply
- 收藏数 favorite
- 投币数 coin
- 分享数 share
- 点赞数 like

每次采集生成一条快照记录，写入 `video_stats_snapshot` 表。

### 4.3.1 采集间隔

默认采集间隔：

```text
300 秒
```

允许用户修改，但下限为：

```text
60 秒
```

如果用户设置低于 60 秒，程序必须拒绝或提示风险，不能实际执行。

---

## 4.4 任务控制

Web 面板需要支持：

- 添加视频任务
- 暂停任务
- 恢复任务
- 删除任务
- 手动立即采集一次
- 查看最近采集状态
- 查看错误日志摘要

任务状态包括：

```text
running
paused
error
stopped
```

任务状态以 `crawl_tasks.status` 为准，`videos` 表只保存视频元数据，不保存调度状态。

---

## 4.5 趋势图表

针对每个视频生成以下图表：

1. 播放量随时间变化折线图
2. 点赞数随时间变化折线图
3. 投币数随时间变化折线图
4. 收藏数随时间变化折线图
5. 评论数随时间变化折线图
6. 弹幕数随时间变化折线图
7. 每小时播放量增量柱状图
8. 每小时点赞增量柱状图

图表要求：

- 横轴为采集时间。
- 纵轴为数值或增量。
- 当数据少于 2 条时，显示“数据不足，继续采集中”。
- 图表应能在本地 Web 页面中查看。

---

## 4.6 HTML 报告导出

每个视频支持一键生成 HTML 报告。

报告内容包括：

1. 视频标题
2. BV 号
3. UP 主名称
4. 发布时间
5. 报告生成时间
6. 采集开始时间
7. 采集结束时间
8. 采集间隔
9. 最新互动数据
10. 各指标增长曲线
11. 每小时增量统计
12. 简单文字结论

示例文字结论：

```text
在本次采集周期内，该视频播放量从 12000 增长至 18500，净增长 6500。
点赞数从 800 增长至 1200，净增长 400。
播放量增长最快的时间段为 14:00–15:00。
```

注意：第一版只做基于数字变化的机械分析，不做复杂 AI 判断。

---

## 5. 数据库设计

使用 SQLite。

数据库路径：

```text
data/bilibili_local.db
```

---

## 5.1 videos 表

用于保存视频基础信息。

```sql
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bvid TEXT NOT NULL UNIQUE,
    aid INTEGER,
    cid INTEGER,
    title TEXT,
    owner_mid INTEGER,
    owner_name TEXT,
    pubdate INTEGER,
    duration INTEGER,
    cover_url TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

---

## 5.2 crawl_tasks 表

用于保存采集任务状态。视频元数据和采集任务必须分离，避免删除任务、暂停任务、失败冷却时污染视频基础信息。

```sql
CREATE TABLE IF NOT EXISTS crawl_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bvid TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'running',
    interval_seconds INTEGER NOT NULL DEFAULT 300,
    next_run_at TEXT,
    last_run_at TEXT,
    last_success_at TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    cooldown_until TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (bvid) REFERENCES videos(bvid)
);
```

索引：

```sql
CREATE INDEX IF NOT EXISTS idx_tasks_status_next_run
ON crawl_tasks(status, next_run_at);
```

状态说明：

```text
running：正常调度
paused：用户暂停
error：连续失败或接口异常，等待用户处理或冷却结束
stopped：软删除，不再调度，但保留历史数据
```

---

## 5.3 video_stats_snapshot 表

用于保存每次采集的互动数据快照。

```sql
CREATE TABLE IF NOT EXISTS video_stats_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bvid TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    view_count INTEGER,
    danmaku_count INTEGER,
    reply_count INTEGER,
    favorite_count INTEGER,
    coin_count INTEGER,
    share_count INTEGER,
    like_count INTEGER,
    raw_json TEXT,
    FOREIGN KEY (bvid) REFERENCES videos(bvid)
);
```

索引：

```sql
CREATE INDEX IF NOT EXISTS idx_stats_bvid_time
ON video_stats_snapshot(bvid, captured_at);
```

---

## 5.4 crawl_logs 表

用于保存采集日志。

```sql
CREATE TABLE IF NOT EXISTS crawl_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bvid TEXT,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);
```

---

## 5.5 第二阶段 comments 模块

第一版只保留代码模块占位，不建 `comments` 表，不实现评论内容采集。

原因：

- 评论内容属于更敏感的数据范围。
- 字段和分页策略需要单独评估。
- 过早建表会误导第一版实现范围，并增加后续迁移成本。

第二阶段确实需要评论采集时，再通过数据库迁移创建表。

参考表结构草案如下，仅供后续版本评审，不得在第一版自动创建：

```sql
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bvid TEXT NOT NULL,
    rpid TEXT NOT NULL,
    parent_rpid TEXT,
    user_mid INTEGER,
    user_name TEXT,
    message TEXT,
    like_count INTEGER,
    reply_count INTEGER,
    ctime INTEGER,
    captured_at TEXT NOT NULL,
    raw_json TEXT,
    UNIQUE(bvid, rpid)
);
```

---

## 5.6 第二阶段 danmaku 模块

第一版只保留代码模块占位，不建 `danmaku` 表，不实现弹幕全文采集。

第二阶段确实需要弹幕采集时，再通过数据库迁移创建表。

参考表结构草案如下，仅供后续版本评审，不得在第一版自动创建：

```sql
CREATE TABLE IF NOT EXISTS danmaku (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bvid TEXT NOT NULL,
    cid INTEGER,
    progress_sec REAL,
    text TEXT,
    send_time INTEGER,
    captured_at TEXT NOT NULL,
    raw_text TEXT
);
```

---

## 6. 网络请求与风控要求

## 6.1 请求客户端

实现统一请求客户端：

```python
class BilibiliClient:
    def __init__(self, timeout: int = 10):
        ...

    async def get_json(self, url: str, params: dict | None = None) -> dict:
        ...
```

要求：

1. 所有请求必须设置 User-Agent。
2. 所有请求必须设置 timeout。
3. 失败时进行有限重试。
4. 重试必须带指数退避。
5. 发生 403、412、验证码、风控提示时，不得继续高频请求。
6. 将错误写入 `crawl_logs`。

---

## 6.2 限速要求

全局请求限制：

```text
同一视频：默认 300 秒一次，不低于 60 秒一次
全局并发请求：最多 2 个
全局最小请求间隔：任意两次真实网络请求之间至少间隔 3 秒
第一版最大 active/running 任务数：10 个
任务调度抖动：在计划时间基础上允许 0-30 秒随机抖动，避免固定节奏请求
连续失败后：至少等待 10 分钟再试
```

连续失败处理：

1. 同一任务连续失败 3 次后，任务进入 `error` 状态或设置 `cooldown_until`。
2. 403、412、验证码、风控、登录要求等情况不应继续重试，应立即进入冷却。
3. 多个任务同时出现风控类错误时，应触发全局冷却，暂停所有自动采集至少 30 分钟。
4. 手动“立即采集”也必须遵守全局并发、全局最小请求间隔和风控冷却。

不得实现：

- 代理池
- IP 轮换
- 自动验证码识别
- 自动登录绕过
- 设备指纹伪造
- 高频秒级请求

---

## 7. 采集模块设计

## 7.1 视频基础信息采集

实现：

```python
async def fetch_video_info(bvid: str) -> VideoInfo:
    ...
```

返回结构：

```python
class VideoInfo(BaseModel):
    bvid: str
    aid: int | None = None
    cid: int | None = None
    title: str | None = None
    owner_mid: int | None = None
    owner_name: str | None = None
    pubdate: int | None = None
    duration: int | None = None
    cover_url: str | None = None
    raw_json: dict | None = None
```

要求：

- 如果视频不存在，抛出明确异常。
- 如果接口字段缺失，不要让程序崩溃。
- 当 `save_raw_json = true` 时，原始响应用 `raw_json` 形式保存在本地，方便后续排错；默认不保存。

---

## 7.2 视频互动数据采集

实现：

```python
async def fetch_video_stats(bvid: str) -> VideoStats:
    ...
```

返回结构：

```python
class VideoStats(BaseModel):
    bvid: str
    view_count: int | None = None
    danmaku_count: int | None = None
    reply_count: int | None = None
    favorite_count: int | None = None
    coin_count: int | None = None
    share_count: int | None = None
    like_count: int | None = None
    captured_at: datetime
    raw_json: dict | None = None
```

---

## 8. Web 面板设计

## 8.1 首页

首页包含：

- 添加视频输入框
- 当前任务总数
- 正在运行任务数
- 最近错误数量
- 视频任务列表

任务列表字段：

| 字段 | 说明 |
|---|---|
| 标题 | 视频标题 |
| BV号 | 视频编号 |
| 状态 | running / paused / error / stopped |
| 采集间隔 | 秒 |
| 最新播放量 | 最近一次快照 |
| 最新点赞数 | 最近一次快照 |
| 最近采集时间 | captured_at |
| 操作 | 查看 / 暂停 / 恢复 / 删除 / 立即采集 |

---

## 8.2 视频详情页

详情页包含：

1. 视频基础信息卡片
2. 最新互动数据卡片
3. 趋势图表
4. 数据快照表格
5. 导出按钮
6. 错误日志

---

## 8.3 设置页

设置项：

- 默认采集间隔
- 最大并发请求数
- 第一版最大 active/running 任务数
- 全局最小请求间隔
- 请求超时时间
- 报告输出目录
- 是否保存 raw_json

第一版不提供局域网访问开关，服务必须只监听 `127.0.0.1`。

后续版本如果加入局域网访问，必须独立评审，并至少包含：

- 默认关闭。
- 用户手动开启后才允许监听 `0.0.0.0`。
- 必须设置访问密码。
- 页面必须显示风险提示：

```text
开启后，同一局域网内设备可能访问本工具页面。请仅在可信网络中使用。
```

---

## 9. 报告生成要求

## 9.1 HTML 报告文件名

格式：

```text
reports/output/{bvid}_{YYYYMMDD_HHMMSS}.html
```

示例：

```text
reports/output/BV1xx411c7mD_20260628_173000.html
```

---

## 9.2 报告结构

```markdown
# B站视频数据分析报告

## 1. 视频信息

## 2. 采集信息

## 3. 最新数据概览

## 4. 趋势图表

## 5. 增量分析

## 6. 简单结论

## 7. 数据说明与限制
```

---

## 9.3 数据说明与限制必须包含

报告末尾必须写明：

```text
本报告基于本地程序在指定时间段内采集到的公开视频公开数据生成。
由于网络波动、接口变化、平台缓存、采样间隔等因素，报告数据可能与页面实时显示存在差异。
本报告仅供个人学习、观察和研究使用。
```

## 9.4 HTML 安全要求

HTML 报告和 Web 页面必须默认转义所有外部来源文本，包括但不限于：

- 视频标题
- UP 主名称
- 封面 URL
- 错误信息
- 后续版本可能加入的评论或弹幕文本

不得用字符串拼接直接生成未转义 HTML。使用 Jinja2 时必须开启自动转义；使用 Plotly 图表时，只允许注入程序生成的图表 HTML，不允许把外部文本作为未转义 HTML 片段插入。

---

## 10. 第二阶段功能：评论采集

第二阶段再实现，第一版不要写死。

### 10.1 评论采集范围

采集公开评论区内容：

- 根评论
- 子评论，数量可配置
- 评论发布时间
- 评论点赞数
- 评论回复数

### 10.2 评论采集限制

默认限制：

```text
每个视频最多采集 500 条根评论
每条根评论最多采集 20 条子评论
评论采集间隔不低于 10 分钟
```

### 10.3 评论分析

后续实现：

- 高频词统计
- 高赞评论排行
- 评论发布时间分布
- 重复评论检测
- 关键词搜索

---

## 11. 第二阶段功能：弹幕采集

第二阶段再实现，第一版不要强行集成。

### 11.1 弹幕采集字段

- 视频内出现时间
- 弹幕文本
- 弹幕发送时间
- 弹幕颜色 / 模式，如果可获得

### 11.2 弹幕分析

- 弹幕密度时间轴
- 高频词统计
- 爆点时间段识别
- 关键词在视频时间轴上的分布

---

## 12. 第三阶段功能：手机局域网访问

第三阶段实现。

不是开发安卓 / 鸿蒙 App，而是在 Windows 本地程序中提供局域网 Web 服务。

要求：

1. 默认只监听 `127.0.0.1`。
2. 用户手动开启后，才允许监听 `0.0.0.0`。
3. 开启局域网访问时显示电脑局域网 IP。
4. 手机浏览器访问：

```text
http://电脑局域网IP:7860
```

5. 局域网访问必须增加访问密码，且默认关闭。

---

## 13. 配置文件

配置文件路径：

```text
config.toml
```

示例：

```toml
[app]
host = "127.0.0.1"
port = 7860

[crawl]
default_interval = 300
min_interval = 60
max_concurrency = 2
max_active_tasks = 10
global_min_request_interval = 3
schedule_jitter_seconds = 30
failure_cooldown_seconds = 600
global_risk_cooldown_seconds = 1800
timeout = 10
save_raw_json = false

[report]
output_dir = "reports/output"

[database]
path = "data/bilibili_local.db"
```

### 13.1 数据保留策略

第一版默认只保存结构化统计字段，`raw_json` 默认关闭。

如果用户开启 `save_raw_json`：

1. 页面必须提示原始响应可能包含当前功能不需要的字段。
2. 原始响应只用于本地排错，不得上传到任何远程服务。
3. 应提供清理能力，例如按视频删除 raw_json，或只保留最近 7 天 / 最近 100 条。
4. 报告导出不得包含完整 raw_json。

---

## 14. 运行方式

### 14.1 开发环境运行

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

### 14.2 Windows 一键运行脚本

创建 `run.bat`：

```bat
@echo off
cd /d %~dp0
call .venv\Scripts\activate
python -m app.main
pause
```

---

## 15. requirements.txt 建议

```text
fastapi>=0.110.0
uvicorn>=0.27.0
httpx>=0.27.0
pydantic>=2.0.0
apscheduler>=3.10.0
plotly>=5.20.0
pandas>=2.0.0
jinja2>=3.1.0
sqlalchemy>=2.0.0
loguru>=0.7.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

---

## 16. 异常处理要求

必须处理：

1. 无效 BV 号
2. 视频不存在
3. 视频不可访问
4. 网络超时
5. 接口返回字段缺失
6. 数据库写入失败
7. 重复添加同一视频
8. 采集任务异常退出
9. 报告生成失败
10. 图表数据不足

错误提示要让用户能看懂。

例如：

```text
该视频暂时无法访问，可能是视频不存在、权限受限或网络请求失败。
```

不要只显示 Python traceback。

---

## 17. 日志要求

日志目录：

```text
logs/app.log
```

日志内容：

- 程序启动
- 添加视频
- 删除视频
- 暂停 / 恢复任务
- 每次采集成功
- 每次采集失败
- 网络异常
- 报告生成
- 数据库异常

日志等级：

```text
INFO
WARNING
ERROR
```

---

## 18. 测试要求

必须提供 pytest 测试。

### 18.1 BV 号解析测试

测试文件：

```text
app/tests/test_bvid_parser.py
```

测试内容：

- 纯 BV 号
- 普通视频链接
- 带查询参数链接
- 非法输入
- 空字符串

---

### 18.2 数据库测试

测试文件：

```text
app/tests/test_database.py
```

测试内容：

- 数据库初始化
- 插入视频
- 重复视频不重复插入
- 创建采集任务
- 暂停 / 恢复 / stopped 状态更新
- 连续失败次数和冷却时间更新
- 插入快照
- 查询快照

---

### 18.3 限速测试

测试文件：

```text
app/tests/test_rate_limit.py
```

测试内容：

- 采集间隔低于 60 秒时拒绝
- 默认间隔为 300 秒
- active/running 任务数超过上限时拒绝新增运行任务
- 任意两次真实请求之间满足全局最小间隔
- 连续失败后进入冷却
- 403、412、验证码、风控类错误不继续重试

---

### 18.4 报告测试

测试文件：

```text
app/tests/test_report.py
```

测试内容：

- 数据不足时报告可以生成
- 多条快照时报告可以生成趋势图
- 输出 HTML 文件存在
- 报告中包含 BV 号、标题、生成时间
- 视频标题、UP 主名称等外部文本必须被 HTML 转义

### 18.5 数据源测试

测试文件：

```text
app/tests/test_data_provider.py
```

测试内容：

- 使用 mock 响应解析视频基础信息。
- 使用 mock 响应解析互动统计字段。
- `code != 0` 时抛出明确异常，不写入成功快照。
- 响应字段缺失时不崩溃，并记录数据不完整。
- 测试不得依赖真实 B站接口。

---

## 19. 验收标准

第一版完成后，必须满足：

### 19.1 基础运行

1. Windows 上能通过 `python -m app.main` 启动。
2. 浏览器能打开本地面板。
3. 程序首次启动能自动创建数据库。
4. 程序关闭后再次启动，历史数据不丢失。
5. 第一版服务只监听 `127.0.0.1`，不得监听 `0.0.0.0`。

### 19.2 视频任务

1. 输入公开视频 BV 号后，能添加任务。
2. 重复添加同一 BV 号时给出提示，不重复创建。
3. 可以暂停、恢复、删除任务。
4. 可以手动立即采集一次。

### 19.3 数据采集

1. 程序能保存视频基础信息。
2. 程序能保存至少以下字段：
   - 播放量
   - 弹幕数
   - 评论数
   - 点赞数
   - 投币数
   - 收藏数
   - 分享数
3. 程序运行 10 分钟后，在默认或手动设置下能产生至少 2 条快照。
4. 网络失败时程序不崩溃。
5. 请求间隔低于 60 秒时，程序拒绝执行。
6. active/running 任务超过 10 个时，程序拒绝继续新增运行任务，或要求用户先暂停其他任务。
7. 出现 403、412、验证码、风控或登录要求时，任务进入冷却或 error 状态，不得继续重试。
8. 测试和主要验收不得依赖真实 B站接口；真实接口只用于用户手动验证。

### 19.4 图表与报告

1. 视频详情页能显示趋势图。
2. 数据少于 2 条时，页面显示“数据不足”。
3. 能导出 HTML 报告。
4. 报告文件能在浏览器中打开。
5. 报告包含数据说明与限制。
6. 报告和页面必须对视频标题、UP 主名称等外部文本做 HTML 转义。

### 19.5 测试

1. `pytest` 能运行。
2. 核心测试通过。
3. 测试不依赖真实 B站接口，应使用 mock 数据。

---

## 20. 手动测试流程

开发完成后，用户按以下流程测试。

### 20.1 启动测试

在项目根目录执行：

```bash
python -m app.main
```

检查：

1. 终端没有报错。
2. 浏览器能打开本地页面。
3. 服务地址应为 `http://127.0.0.1:7860` 或 `http://localhost:7860`，第一版不得提示局域网 IP。
4. 项目目录下出现：

```text
data/bilibili_local.db
logs/app.log
```

---

### 20.2 添加视频测试

1. 找一个公开视频。
2. 复制 BV 号或视频链接。
3. 在首页输入框中提交。
4. 检查任务列表是否出现该视频。
5. 检查标题、UP 主、状态是否显示正常。

预期结果：

```text
视频添加成功，状态为 running。
```

---

### 20.3 重复添加测试

再次输入同一个 BV 号。

预期结果：

```text
提示该视频已存在，不创建重复任务。
```

---

### 20.4 立即采集测试

点击“立即采集”。

预期结果：

1. 页面提示采集成功。
2. 最新播放量、点赞数等字段更新。
3. 数据库中新增一条快照。

可用 SQLite 工具或程序内表格查看。

---

### 20.5 定时采集测试

将采集间隔设置为 60 秒。

等待数分钟后检查：

1. 快照数量是否增加。
2. 采集时间是否合理。
3. 日志是否有成功记录。

---

### 20.6 限速测试

尝试将采集间隔设置为：

```text
10 秒
```

预期结果：

```text
程序拒绝保存，并提示采集间隔不得低于 60 秒。
```

---

### 20.7 暂停 / 恢复测试

1. 点击暂停。
2. 等待一个采集周期。
3. 检查快照数量是否停止增长。
4. 点击恢复。
5. 检查采集是否继续。

---

### 20.8 删除任务测试

1. 点击删除任务。
2. 检查任务列表是否移除。
3. 历史数据可以保留，不强制物理删除。

建议实现软删除或 stopped 状态，不要默认删除历史数据。

---

### 20.9 报告生成测试

1. 进入视频详情页。
2. 点击“生成报告”。
3. 检查 `reports/output/` 目录。
4. 用浏览器打开 HTML 文件。

预期报告包含：

- 视频标题
- BV 号
- 采集时间范围
- 最新数据
- 图表
- 简单结论
- 数据说明与限制

---

### 20.10 断网测试

1. 启动程序并添加视频。
2. 暂时断开网络。
3. 点击立即采集或等待定时采集。
4. 检查程序是否崩溃。

预期结果：

```text
程序不崩溃，页面显示采集失败，日志记录网络错误。
```

---

### 20.11 重启测试

1. 关闭程序。
2. 重新运行：

```bash
python -m app.main
```

3. 检查任务和历史快照是否还在。

预期结果：

```text
历史任务和数据不丢失。
```

---

## 21. 不允许 Codex 实现的内容

Codex 不得实现以下功能：

1. 自动验证码识别。
2. 自动登录多个账号。
3. 代理池。
4. IP 轮换。
5. 模拟移动端设备指纹。
6. 绕过风控。
7. 秒级批量抓取。
8. 采集私密、付费、会员限制内容。
9. 将用户 Cookie 上传到任何远程服务。
10. 默认开启局域网公开访问。
11. 在接口异常、风控、登录要求或字段变化时自动搜索、切换、拼接新的非授权接口。
12. 为了继续采集而模拟移动端签名、设备参数、客户端指纹或其他绕过机制。

如果需要登录态 Cookie，必须：

- 让用户手动粘贴。
- 明确提示风险。
- 本地加密保存。
- 支持一键删除。
- 默认不启用。

第一版建议完全不实现 Cookie。

---

## 22. Codex 开发步骤建议

请 Codex 按以下顺序开发，不要跳步。

### Step 1：项目骨架

完成：

- 目录结构
- requirements.txt
- README.md
- run.bat
- 配置文件
- 日志系统

### Step 2：数据库

完成：

- SQLite 初始化
- videos 表
- crawl_tasks 表
- video_stats_snapshot 表
- crawl_logs 表
- 基础增删查改

### Step 3：BV 号解析

完成：

- `parse_bvid`
- 单元测试

### Step 4：采集客户端

完成：

- DataProvider 抽象
- mock 响应样例和字段映射
- BilibiliClient
- timeout
- retry
- backoff
- error logging
- 风控类错误失败关闭

### Step 5：视频信息与快照采集

完成：

- fetch_video_info
- fetch_video_stats
- 保存到数据库

### Step 6：任务调度

完成：

- 添加任务
- 暂停任务
- 恢复任务
- 删除任务
- 手动采集
- 最大 active/running 任务数限制
- 全局最小请求间隔
- 失败冷却和全局风控冷却

### Step 7：Web UI

完成：

- 首页
- 任务列表
- 视频详情页
- 设置页
- 第一版只监听 127.0.0.1，不提供局域网访问开关

### Step 8：图表

完成：

- 趋势折线图
- 增量柱状图
- 数据不足提示

### Step 9：报告

完成：

- HTML 模板
- 报告导出
- 报告打开测试

### Step 10：测试与修复

完成：

- pytest
- mock 网络请求
- 手动测试
- README 补充

---

## 23. 给 Codex 的直接指令

可以直接把下面这段交给 Codex：

```text
请根据当前 Markdown 文档开发一个 Windows 本地运行的 B站公开视频数据采集与分析工具。

要求：
1. 第一版只做 Windows 本地程序，不做安卓/鸿蒙原生 App。
2. 使用 Python 3.11+。
3. 推荐使用 FastAPI + Jinja2 + SQLite + httpx + APScheduler + Plotly。
4. 先实现 DataProvider 抽象和 mock 响应字段映射，不得在开发过程中临时搜索、拼凑或自动切换接口。
5. 实现输入 BV 号或视频链接后添加采集任务。
6. 定时采集公开视频的播放量、弹幕数、评论数、点赞数、投币数、收藏数、分享数。
7. 保存每次采集快照到 SQLite。
8. 提供本地 Web 面板，支持添加、暂停、恢复、删除、立即采集。
9. 提供趋势图表和 HTML 报告导出。
10. 请求间隔不得低于 60 秒。
11. 全局最小请求间隔不得低于 3 秒，第一版 active/running 任务数不得超过 10 个。
12. 所有网络请求必须有 timeout、有限重试、指数退避、错误日志；403、412、验证码、风控、登录要求等情况必须失败关闭或进入冷却。
13. 不得实现代理池、验证码绕过、自动登录、多账号、设备指纹伪造、高频抓取。
14. 第一版不实现评论全文采集和弹幕全文采集，只预留模块，不创建评论和弹幕内容表。
15. 第一版只监听 127.0.0.1，不实现局域网手机访问开关。
16. HTML 页面和报告必须转义所有外部来源文本。
17. 提供 README、requirements.txt、run.bat 和 pytest 测试，测试必须使用 mock 数据，不依赖真实 B站接口。
18. 开发完成后，按照文档中的验收标准逐项自检。

请按文档第 22 节的步骤逐步实现，每完成一个阶段先运行测试，再进入下一阶段。
```

---

## 24. README 必须包含的内容

Codex 生成的 README.md 至少包含：

1. 项目简介
2. 功能范围
3. 不支持内容
4. 安装方法
5. 启动方法
6. 添加视频方法
7. 生成报告方法
8. 数据保存位置
9. 日志位置
10. 常见问题
11. 合规与使用限制
12. 数据源说明与接口可能变化的风险
13. 第一版仅支持本机 `127.0.0.1` 访问，不支持局域网访问
14. raw_json 默认关闭及清理方式

---

## 25. 第一版完成后的下一步

第一版稳定后，再考虑：

1. 评论采集
2. 弹幕采集
3. 高频词统计
4. 弹幕密度时间轴
5. 局域网手机访问
6. 简单访问密码
7. 打包成 exe
8. 安卓 / 鸿蒙控制端

不要在第一版直接实现所有功能。
