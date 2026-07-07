# Android端规划

## 当前结论

Android 端从 `v0.3.0` 开始进入 MVP。`v0.2.0` 只做规划、schema 和文档，不创建完整 Android 业务代码。

## MVP 第一阶段范围

只做：

1. 输入 BV 号或视频链接。
2. 解析 BV 号。
3. 手动刷新获取基础视频数据。
4. 本地 Room 数据库保存快照。
5. 列表页展示视频。
6. 详情页展示最近一次快照。
7. 简单历史趋势图。
8. 导出 JSON / CSV。
9. 本地日志页面。

暂不做：

1. 高频后台监控。
2. 自动绕过登录。
3. 验证码处理。
4. 代理池。
5. Cookie 自动抓取。
6. 评论全文大规模抓取。
7. 弹幕全文大规模抓取。
8. 鸿蒙端。
9. 云端同步。
10. 付费服务器。

## 推荐技术路线

- Kotlin：主语言，减少 Java 模板代码。
- Android Studio：标准构建和实机调试环境。
- Jetpack Compose：MVP 页面简单，适合快速迭代。
- Room：本地 SQLite，适合快照历史和日志。
- OkHttp：MVP 阶段比 Retrofit 更轻，后续接口稳定后可再封装。
- kotlinx.serialization：JSON 导入导出和 schema 对齐。
- WorkManager：只用于后续低频任务，不作为 MVP 首要目标。
- 图表库：优先评估 MPAndroidChart 的稳定性；若 Compose 图表库维护不足，不要为了纯 Compose 强行采用。

## 不推荐技术路线

- WebView 包装 Windows 页面：不能解决本地 Room、导出、通知和后台限制，调试成本更高。
- React Native：后台任务、前台服务、Room、权限都要桥接，当前收益不足。
- Flutter：UI 可行，但原生后台和通知仍需平台代码；对这个 MVP 不是最小路径。
- Java 原生：可行但 Compose 和 Kotlin 生态更适合后续维护。
- 隐藏保活方案：不可靠，也不符合项目边界。

## 页面结构

- 首页：视频列表、最近刷新时间、失败状态。
- 添加页：输入 BV 号或链接，显示解析错误。
- 详情页：视频基础信息、最近一次快照、简单趋势图。
- 导出页：导出 JSON / CSV，显示本地文件路径。
- 日志页：本地请求、解析、数据库和导出日志。
- 设置页：刷新超时、最低间隔、数据清理。

## 数据流

1. 输入文本。
2. 解析为 `bv_id`。
3. OkHttp 请求公开数据源。
4. 响应映射为 shared schema 字段。
5. Room 写入视频基础信息和快照。
6. UI 从 Room 读取并展示。
7. 导出模块按 `shared/data_schema/` 输出 JSON / CSV。

## Room 表建议

- `videos`
- `video_snapshots`
- `crawl_logs`
- `export_records`

字段必须参考 `docs/数据结构说明.md` 和 `shared/data_schema/`。

## 网络请求规则

- 固定公开数据源。
- 设置超时。
- 遇到 403、412、验证码、风控、登录要求或异常结构时标记失败。
- 不自动寻找替代接口。
- 不注入 Cookie。
- 不伪造设备指纹。

## 日志方案

本地日志至少记录：

- 时间
- 操作类型
- `bv_id`
- 请求状态
- 错误类型
- 简短错误信息

不得记录 Cookie、账号、密码、完整敏感响应。

## 实机调试步骤

1. 安装 debug APK。
2. 输入一个公开视频 BV 号。
3. 手动刷新。
4. 检查详情页最新快照。
5. 检查 Room 数据。
6. 导出 JSON / CSV。
7. 与 `shared/data_schema/` 对照字段。
8. 记录到 `docs/实机测试记录.md`。

## 版本路线图

- `v0.3.0`：Android MVP 工程、BV 解析、Room schema、手动刷新。
- `v0.3.1`：列表页、详情页、最近快照展示。
- `v0.3.2`：趋势图、JSON / CSV 导出。
- `v0.3.3`：日志页和错误状态。
- `v0.4.0`：WorkManager 低频任务和前台服务通知。
- `v0.5.0`：Windows + Android 数据格式统一验证。

