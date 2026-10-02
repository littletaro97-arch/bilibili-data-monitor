# Windows 0.12.0 · installer.1

本版采用自有窗口 + WebView2 Evergreen Runtime，不捆绑完整浏览器内核。缺少运行时时提供微软安装入口并回退到浏览器。

- 关闭窗口隐藏到托盘，隐藏/最小化时跳过面板刷新；托盘唤回窗口、立即检测、进入设置、浏览器打开及退出。
- 回收站停止链接检测并保留历史，取回按原间隔恢复，遵守运行任务上限。
- 支持 BV、完整视频链接及 b23.tv 短链；打开视频继续使用默认浏览器，按用户定义已满足打开入口。
- 详情封面与响应式布局；设置页检查 GitHub Windows 安装包、说明和校验后下载。
- 稳定 AppId、同用户原安装记录存在时默认沿用目录，升级/卸载保留业务数据。

安装包：`BilibiliMonitor-v0.12.0-installer.1-windows-x64-setup.exe`。Windows 10/11 x64，无需另装 Python；未进行 Authenticode 签名。

用户数据：`%LOCALAPPDATA%\BilibiliMonitor\runtime-data`。本轮没有修改 Android 或发布新 APK；原 Android Release 继续保留。

验证：122 项 Windows 测试；真实 Evergreen 窗口正常启动、隐藏/恢复、重复启动激活、正常退出与启动中退出；安装到隔离中文目录、安装文件哈希与扫描目录一致、原目录升级、报告/导出、重复运行、卸载与数据保留。不是干净 Windows 虚拟机/所有 OEM 或人工逐页向导验收。

测试阶段发现过 WebView 初始化前清理错误，以及 pythonnet 3.2.0 下的打包退出异常，失败安装包仅保存在本地 attempt 目录，不用于发布。最终版本使用独立缓存目录并固定 pythonnet 3.0.5，退出不再等待服务关闭后可能无法完成的页面加载；移除同步等待页面 JavaScript 回调，通过轻量可见状态查询在隐藏时停止业务刷新，发布前重新验收。

源码基线 `10c2572`，功能提交 `0c695eb`，桥接版本固定提交 `c9a4b4c`，退出/刷新修复 `190ba4b`、`6813dfc`；本次分支 `codex/windows-desktop-release`。回退代码使用 `git revert`，不要重置用户数据。敏感信息检查见 `SECURITY-AUDIT.md`；安装验证和大小/摘要见同目录记录。
