# v0.4.0 Android Stability Changelog

## 新增功能

- 新增 `scripts/android-build-ascii.ps1`，固定 Android ASCII junction 构建流程。
- 新增 v0.4.0 Debug APK 输出目录和 release 记录。
- 新增 v0.3.0 用户手动实机反馈记录。
- 新增 v0.4.0 实机测试模板。

## 修改内容

- Android `versionName` 升为 `0.4.0`，`versionCode` 升为 `8`。
- 导出 JSON/CSV 成功后显示文件名、导出时间和绝对路径。
- 网络错误提示细化为无网络/DNS、超时、HTTP 403、HTTP 412、登录限制、验证码、风控、字段缺失、JSON 解析失败等场景。
- 日志级别统一为 `info` / `warning` / `error`。
- 关键操作写日志：BV 解析、网络请求、数据库写入、导出成功/失败。
- 详情页刷新和导出按钮增加 loading 防重复点击。
- 历史页、日志页、首页补充空状态提示。

## 修复问题

- 固化中文路径下 Android unit test `ClassNotFoundException` 的规避方式。
- 改善导出成功反馈不完整的问题。
- 改善网络错误提示过粗的问题。
- 改善刷新/导出操作可重复点击的问题。

## 已知问题

- Codex 未进行 v0.4.0 实机安装测试，等待用户安装验证。
- 原中文路径下直接运行 Android unit test 仍可能触发 JDK/Gradle `@argfile` classpath 问题；应使用 `scripts/android-build-ascii.ps1`。
- 导出仍位于 app external files 目录，部分手机文件管理器可见性需要实机验证。
- 未引入 WorkManager、趋势图增强或后台采集。

## 下一步计划

- 如果 v0.4.0 实机发现 bug，进入 v0.4.1 定点修复。
- 如果 v0.4.0 稳定，v0.5.0 再评估低频 WorkManager 和趋势图增强。
- 继续禁止登录绕过、Cookie、验证码处理、代理池、风控绕过和高频后台采集。
