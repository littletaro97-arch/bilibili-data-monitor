# v0.3.0 Android MVP Changelog

## 新增功能

- 新增 Android 原生 Gradle 工程，位于 `android/`。
- 新增 Compose MVP 页面：视频输入、详情、历史、导出、日志。
- 新增 BV 号和 Bilibili 视频链接解析。
- 新增手动刷新公开视频基础数据。
- 新增 Room 本地数据库，保存视频、快照和日志。
- 新增 JSON/CSV 导出。
- 新增 Debug APK 打包。

## 修复问题

- 新建 Android 单元测试覆盖 BV 解析、接口 JSON 映射和 CSV 输出。
- 记录中文路径下 Gradle/JDK `@argfile` 导致 unit-test `ClassNotFoundException` 的本机问题，并使用临时 ASCII junction 完成验证。

## 已知问题

- 未进行实机安装测试。
- UI 仍是 MVP，没有复杂趋势图。
- 导出路径位于应用 external files 目录，真实设备可访问性需要 v0.4.0 验证。
- 遇到登录、验证码、403、412 或风控限制时只记录失败，不绕过。
- 原中文路径下直接运行 Android unit test 可能失败；本机通过 ASCII junction 验证。

## 下一步计划

- v0.4.0 优先做实机安装调试。
- 优化 UI 可用性和错误提示。
- 验证 Room 数据和导出路径。
- 评估低频 WorkManager，但不做高频后台监控。
