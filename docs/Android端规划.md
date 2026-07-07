# Android端规划

## MVP 目标

Android MVP 只做低频、透明、本地优先的数据查看与记录，不做绕过登录、验证码、风控、代理池、高频采集或隐藏后台长期运行。

第一阶段能力：

- 手动输入 Bilibili 视频链接或 BV 号。
- 获取公开视频基础信息。
- 获取播放、点赞、投币、收藏、评论数、弹幕数等公开基础数据。
- 支持手动刷新。
- 支持低频定时刷新。
- 本地保存历史记录。
- 显示简单趋势图。
- 支持导出 CSV / JSON。
- 支持前台服务通知。
- 提供本地日志页面，方便实机 debug。

## 推荐技术栈

- Kotlin：Android 长期维护首选语言。
- Jetpack Compose：适合快速构建表单、列表、详情页和设置页。
- Room：本地 SQLite 抽象，适合历史快照和任务表。
- WorkManager：低频、可约束的后台任务。
- Foreground Service：用户可见的刷新状态与长任务提示。
- OkHttp 或 Retrofit：网络请求、超时、拦截器和错误处理清晰。
- kotlinx.serialization：CSV/JSON 导出前的数据模型序列化。
- MPAndroidChart 或 Compose 图表库：先用简单折线图，不做复杂交互图表。

## 不推荐技术栈

- WebView 包装 Windows 端页面：不能解决本地存储、后台任务、通知和 Android 系统限制，调试也更差。
- React Native：本项目核心风险在后台任务、前台服务、Room、权限和系统限制，跨端层会增加原生桥接成本。
- Flutter：可做 UI，但后台调度、前台服务、通知和平台限制仍要写大量原生代码；当前收益不如 Kotlin 原生。
- Java 原生：可行但开发效率和 Compose 生态不如 Kotlin。
- 隐藏后台保活方案：不可靠，也容易触碰系统和平台边界。

## 页面结构

- 首页：视频任务列表、最新数据、刷新状态。
- 添加视频页：输入 BV 号或链接，校验格式。
- 视频详情页：基础信息、最新快照、趋势图、历史记录。
- 导出页：导出 CSV / JSON，显示文件位置。
- 日志页：网络请求、任务调度、错误和风控提示。
- 设置页：刷新间隔、仅 Wi-Fi、通知开关、数据清理。

## 数据流

1. 用户输入 BV 号或链接。
2. 解析为标准 BV 号。
3. 请求公开视频基础接口。
4. 将视频信息写入 Room。
5. 手动刷新或 WorkManager 触发低频刷新。
6. 将统计快照写入 Room。
7. UI 观察 Room 数据并刷新图表。
8. 导出模块从 Room 查询并生成 CSV / JSON。

## 本地数据库方案

建议表：

- `videos`：视频基础信息。
- `crawl_tasks`：刷新任务、状态、间隔和失败信息。
- `video_stats_snapshot`：统计快照。
- `crawl_logs`：本地日志。

字段应尽量对齐 Windows 端 SQLite：

- `bvid`
- `aid`
- `cid`
- `title`
- `owner_mid`
- `owner_name`
- `captured_at`
- `view_count`
- `danmaku_count`
- `reply_count`
- `favorite_count`
- `coin_count`
- `share_count`
- `like_count`
- `online_count`
- `online_text`
- `source_type`
- `source_note`

## 网络请求方案

- 固定公开数据源，不自动拼接或切换未知接口。
- 每个请求必须设置超时。
- 遇到 403、412、验证码、风控、登录要求或异常结构时停止任务或进入冷却。
- 不自动寻找替代接口。
- 不伪造设备指纹。
- 不注入 Cookie。

## 定时任务方案

- 使用 WorkManager 做低频任务。
- 默认间隔不低于 Windows 端最低间隔。
- 支持仅 Wi-Fi、充电时执行等约束。
- Android 系统可能推迟任务，UI 必须明确显示“计划时间”和“实际执行时间”。

## 前台服务与通知方案

- 只有用户明确开启低频监控时显示前台服务通知。
- 通知显示当前任务数量、最近刷新时间、最近错误。
- 通知必须可停止。
- 不承诺隐藏后台稳定长期运行。

## 日志方案

- 本地 `crawl_logs` 表保存关键事件。
- 日志页按时间倒序展示。
- 日志包含请求目标类型、错误类型、冷却原因和任务 ID。
- 不记录 Cookie、账号、密码、完整敏感响应。

## 与 Windows 端共享的数据格式

第一阶段共享 CSV / JSON 字段，不共享数据库文件。

建议导出字段：

```text
bvid,captured_at,view_count,danmaku_count,reply_count,favorite_count,coin_count,share_count,like_count,online_count,online_text,source_type,source_note
```

后续在 `shared/data_schema/` 固化 schema，再让 Windows 和 Android 双端共同遵守。

## 实机调试步骤

1. 安装 debug APK。
2. 清空旧数据或记录迁移状态。
3. 输入一个公开视频 BV 号。
4. 手动刷新并查看日志。
5. 切换网络后重试。
6. 开启低频定时刷新。
7. 锁屏等待 WorkManager 执行窗口。
8. 查看前台服务通知是否可见且可停止。
9. 导出 CSV / JSON 并与 Windows 字段对齐。

## 版本路线图

- `v0.3.0`：Android MVP 空工程、Room schema、BV 解析、手动刷新。
- `v0.3.1`：趋势图和导出 CSV / JSON。
- `v0.3.2`：日志页和错误冷却展示。
- `v0.4.0`：WorkManager、前台服务通知、实机后台限制验证。
- `v0.5.0`：Windows + Android 共享数据格式冻结。

