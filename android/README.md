# Android 端

本目录是 Android 原生应用工程，和根目录 `app/` 的 Windows/Python 端隔离维护。

- 根目录 `app/`：Windows/Python 后端、页面、采集与测试。
- `android/app/`：Android 原生应用模块。
- `shared/`：仅放双端共享 schema 和说明，不放 Android 私有代码。

## v0.3.0 MVP 范围

v0.3.0 提供 Android MVP 原型：

- 输入 BV 号或 Bilibili 视频链接。
- 解析 BV 号。
- 手动刷新基础视频数据。
- 展示视频基础信息和最新快照。
- 使用 Room 保存视频、快照和本地日志。
- 展示历史快照列表。
- 支持 JSON/CSV 导出。
- 显示基础错误信息。
- 生成 Debug APK。

本版本不包含 WorkManager、前台服务、高频后台采集、登录、验证码处理、Cookie、代理池或任何风控绕过逻辑。

## 构建

本工程使用 Gradle Wrapper：

```powershell
cd android
.\gradlew.bat test
.\gradlew.bat assembleDebug
```

正式打包优先使用根目录脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\android-build-ascii.ps1
```

该脚本会通过 `C:\Users\LittleTaro\codex-bilibili-monitor-ascii\android` 执行测试和构建，并把 Debug APK 复制到对应版本的 `releases/android/` 目录。
从 v0.7.0 起，该脚本还会执行 `lintDebug`。

如果项目位于包含中文字符的 Windows 路径，JDK/Gradle 的测试 worker `@argfile` 可能无法正确加载 unit-test classpath，表现为 `ClassNotFoundException`。本机验证时使用临时 ASCII junction 指向同一仓库后执行 Android 测试和打包。

APK 输出位置：

```text
releases/android/v0.3.0/bilibili-monitor-android-v0.3.0-debug.apk
```

v0.4.0 输出位置：

```text
releases/android/v0.4.0/bilibili-monitor-android-v0.4.0-debug.apk
```

v0.5.0 输出位置：

```text
releases/android/v0.5.0/bilibili-monitor-android-v0.5.0-debug.apk
```

v0.5.1 输出位置：

```text
releases/android/v0.5.1/bilibili-monitor-android-v0.5.1-debug.apk
```

v0.6.0 输出位置：

```text
releases/android/v0.6.0/bilibili-monitor-android-v0.6.0-debug.apk
```

v0.7.0 输出位置：

```text
releases/android/v0.7.0/bilibili-monitor-android-v0.7.0-debug.apk
```

v0.8.0 输出位置：

```text
releases/android/v0.8.0/bilibili-monitor-android-v0.8.0-debug.apk
```

v0.9.0 输出位置：
```text
releases/android/v0.9.0/bilibili-monitor-android-v0.9.0-debug.apk
```

v0.9.1 输出位置：
```text
releases/android/v0.9.1/bilibili-monitor-android-v0.9.1-debug.apk
```

## v0.5.0 范围

v0.5.0 增加低频后台刷新和趋势展示，但仍不扩大采集边界：

- 自动刷新默认关闭，必须在设置页手动开启。
- 使用 WorkManager，间隔限制为 15 分钟、30 分钟、1 小时、3 小时、6 小时。
- WorkManager 由 Android 系统调度，可能被省电策略延迟或合并，不保证准点执行。
- 自动刷新只刷新 Room 中已经添加的视频，不发现新视频，不采集评论/弹幕。
- 不实现登录、Cookie、验证码处理、代理池、风控绕过或高频保活。
- 设置项使用 DataStore；Room schema 未变化，数据库版本仍为 1。
- 历史页使用本地快照绘制简单 Compose Canvas 趋势图，支持最近 20/50 条。
- 导出页显示文件名、路径、大小、时间，并通过 FileProvider 调用 Android Sharesheet 分享文件。

## v0.5.1 热修复范围

v0.5.1 只修复自动刷新设置可达性和状态可观测性，不扩大采集范围：

- 顶部导航使用可横向滚动列表，避免“设置”按钮在窄屏被裁掉。
- 首页新增“自动刷新设置”入口。
- 设置页显示 WorkManager 是否已注册，以及最近注册、取消、开始、结束、结果、错误。
- DataStore 记录自动刷新诊断状态，便于实机判断是否注册、是否等待系统调度、是否执行失败。
- 不引入高频后台任务，不做隐藏保活，不采集评论/弹幕，不处理登录、Cookie、验证码或风控。

## v0.6.0 诊断增强范围

v0.6.0 只增强自动刷新可观测性和手动 debug 工具：

- 设置页诊断区显示 unique work name、约束、最近状态和累计成功/失败次数。
- “测试自动刷新一次”按钮手动执行一次自动刷新同范围逻辑。
- “刷新所有已添加视频”按钮手动批量刷新本地已有视频。
- 日志页提供基础筛选。
- 不新增循环任务，不降低 WorkManager 周期，不做隐藏保活。

## v0.7.0 导航、导出和设置页修复范围

v0.7.0 只修复 Android 端可用性和系统存储交互：

- 顶部导航根据是否选中视频动态显示；无选中视频时隐藏详情和历史。
- App 外层适配安全绘制区域，降低状态栏、刘海屏、挖孔屏遮挡风险。
- 直接导出走 Android Storage Access Framework：首次必须打开系统保存窗口，默认目录通过目录授权单独设置。
- 默认目录直存会避开同名覆盖；授权失效时清理默认目录并回到系统保存窗口。
- 原分享导出继续通过 FileProvider 和系统分享面板工作。
- 设置页按功能分类重排，网络约束开关整行可点击并右侧对齐。
- 不新增采集范围，不处理登录、Cookie、验证码、代理池或风控绕过。

## v0.8.0 崩溃和滚动布局修复范围

v0.8.0 继续保持单 Activity、`Page` enum 和本地 Compose 状态管理，不引入 Navigation Compose 或 ViewModel 重构：

- 修复高级页崩溃：高级页日志列表并入同一个主 `LazyColumn`，不再嵌套竖向懒列表。
- 首页、详情、历史、设置、高级页面都使用有界主滚动容器。
- 最近快照跟随详情页完整滚动，避免底部内容不可见。
- 首页移除自动刷新设置入口，自动刷新配置集中在设置页。
- 自动刷新间隔使用固定档位滚轮选择器。
- 低于 15 分钟的间隔只保存为用户选择；后台 WorkManager 周期按 Android 最小 15 分钟执行。
- 长标题、日志详情、错误详情和诊断区支持展开 / 收起。
- 不新增高频后台任务、不做隐藏保活、不采集评论/弹幕、不处理登录、Cookie、验证码或风控。

## v0.9.0 通知提醒和后台引导范围

v0.9.0 继续使用 WorkManager 做低频后台检测，不引入常驻前台服务：

- 设置页新增通知提醒分组，包含通知总开关、系统权限状态、每次检测提醒、定时汇总提醒和系统通知设置入口。
- Android 13 及以上先展示应用内用途说明，再由用户决定是否请求通知权限；拒绝权限后核心功能继续可用。
- 自动检测完成后按设置发送单条合并通知；空视频列表不发送空提醒。
- 定时汇总通知间隔按 5 分钟步进，且不得短于当前 WorkManager 实际后台检测间隔。
- 设置页新增后台运行分组，展示 WorkManager 状态、通知权限、电池优化状态、最近执行结果和系统设置入口。
- 后台权限、电池优化和厂商自启动均为可选配置，不强制授权，也不承诺永不被系统杀后台。
- 检测间隔和通知汇总间隔共用重做后的滚轮组件，滚动停止后才保存稳定值。
- Room schema 未变化，数据库版本仍为 1；DataStore 新增通知和后台引导字段。

## v0.9.1 v9 测试前阻断修复范围

v0.9.1 是 v0.9.0 之后的测试候选 hotfix，不覆盖 v0.9.0：

- 修复移动端哔哩哔哩分享文案、移动端链接和短链接无法添加的问题。
- 纯 BV、桌面端标准链接、移动端链接、带参数链接和精准空降链接继续通过本地解析器处理。
- 短链接只在本地解析失败后通过现有 OkHttp 网络层解析，运行在 Repository 的 IO 路径，不在 UI 主线程同步请求。
- 设置页检测间隔和通知汇总间隔默认收缩为摘要，用户点击编辑后才展开滚轮。
- 滚轮展开状态只是界面临时状态，不写入 DataStore；数值仍只在稳定选择后保存。
- 新采集、日志、导出和后台任务时间使用设备本机 OffsetDateTime；UI 按当前设备时区格式化展示。
- Room schema 未变化，数据库版本仍为 1。
