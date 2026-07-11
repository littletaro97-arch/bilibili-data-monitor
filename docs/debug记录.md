# debug记录

## 记录模板

### YYYY-MM-DD 问题标题

- 版本/分支：
- 运行环境：
- 触发步骤：
- 期望结果：
- 实际结果：
- 错误日志：
- 初步判断：
- 修改范围：
- 验证命令：
- 验证结果：
- 回滚方式：
- 后续风险：

## Windows 启动失败排查

1. 在项目根目录运行 `python -m app.main`。
2. 如果没有输出，确认 Python 和依赖：`python --version`、`pip install -r requirements.txt`。
3. 如果使用 `run.bat` 且隐藏 CMD，查看 `logs/launcher.log`。
4. 如果进入应用启动后失败，查看 `logs/app.log`。

## 端口占用排查

1. 运行：

```powershell
netstat -ano | findstr :7860
```

2. 如果已有进程占用，先确认是否是本程序。
3. 不要直接杀未知进程；先记录 PID、进程名和启动时间。

## LAN 暴露风险排查

1. 检查 `config.toml` 的 `[lan].enabled`。
2. 本机调试应为 `false`。
3. 如果为 `true`，启动会监听 `0.0.0.0:7860`，只应在可信局域网临时使用。
4. 检查日志中是否有 LAN 风险提示。
5. 确认 `config.toml` 未进入 Git。

## B 站接口字段变化排查

1. 查看页面日志中的 `接口返回失败`、`接口响应结构异常`、`网络请求失败`。
2. 区分网络错误、字段缺失、风控返回。
3. 字段缺失时优先让字段为 `null`，不要伪造 0。
4. 不临时拼接未知接口，不绕过登录、验证码或风控。
5. 新增字段前先更新 `shared/data_schema/`。

## 数据库异常排查

1. 确认数据库路径：`data/bilibili_local.db`。
2. 确认文件未被 Excel、备份软件或其它进程锁定。
3. 先复制数据库备份，再执行修复或迁移。
4. 不把数据库提交到 Git。

## 采集失败排查

1. 查看视频详情页日志和设置页日志。
2. 查看 `logs/app.log`。
3. 检查任务是否处于冷却。
4. 检查是否返回 403、412、验证码、登录或风控信息。
5. 如果是平台限制，停止任务或等待冷却，不尝试绕过。

## 测试失败排查

1. 运行 `python -m pytest -x` 定位首个失败。
2. 网络相关测试必须 mock，不依赖真实 B 站请求。
3. 不删除测试来通过验证。
4. 修复后再运行完整 `python -m pytest`。

## Android v0.3.0 排查记录

### Android Studio 打不开工程

1. 只打开 `android/` 目录，不要把根目录 `app/` 当成 Android 模块。
2. 确认 JDK 可用，本机验证使用 JDK 21。
3. 确认 `android/local.properties` 存在且只保留在本机，不提交 Git。

### Gradle Sync 失败

1. 确认使用 `android/gradlew.bat`，不要依赖不明确的全局 Gradle。
2. 确认 Android SDK 路径有效：`C:\Users\LittleTaro\AppData\Local\Android\Sdk`。
3. 如果提示 compileSdk 35 支持问题，先确认本机 SDK 已安装 API 35。

### SDK 缺失

1. 打开 Android Studio SDK Manager 安装 Android SDK Platform 35。
2. 安装 Build Tools 和 Platform Tools。
3. 更新 `android/local.properties`，不要提交该文件。

### APK 构建失败

1. 在 `android/` 下运行 `.\gradlew.bat assembleDebug --stacktrace`。
2. 查看 `android/app/build/reports/` 和 Gradle 输出。
3. 不要通过删除功能或跳过编译来制造成功结果。

### 实机安装失败

1. 确认设备允许安装调试 APK。
2. 确认 Android 版本不低于 minSdk 26。
3. 用 `adb install -r releases/android/v0.3.0/bilibili-monitor-android-v0.3.0-debug.apk` 复测。
4. 记录设备型号、Android 版本和错误输出到 `docs/实机测试记录.md`。

### 网络请求失败

1. 检查网络连接。
2. 检查是否返回 403、412、登录、验证码或风控限制。
3. 遇到平台限制只记录失败，不绕过、不加 Cookie、不使用代理池。

### Room 数据库异常

1. 清理应用数据后复测。
2. 检查实体字段和 DAO 查询是否匹配。
3. 保留失败日志，不提交设备数据库。

### BV 解析失败

1. 确认输入包含 `BV` 开头的 12 位 BV 号。
2. 支持直接输入 BV 号或 `https://www.bilibili.com/video/BV...` 链接。
3. 无效输入应显示错误并写入本地日志。

### 导出文件找不到

1. v0.3.0 导出到应用 external files 下的 `exports` 目录。
2. 页面会显示导出文件绝对路径。
3. 实机上如不可见，v0.4.0 需要改进分享或系统文件选择器导出。

### 中文路径下 Android 单测 ClassNotFound

本机正式目录包含中文字符。直接在该路径运行 Android unit test 时，JDK/Gradle worker `@argfile` 可能无法正确加载测试 classpath，表现为：

```text
ClassNotFoundException: com.littletaro.bilibilimonitor.data.BvParserTest
```

本轮验证使用临时 ASCII junction：

```text
C:\Users\LittleTaro\codex-bilibili-monitor-ascii
```

该 junction 指向正式仓库，不改变代码归属。后续若要彻底解决，应评估升级 Gradle/AGP/JDK 组合，或将 Android 构建工作区放在 ASCII 路径。

## Android v0.4.0 固化构建流程

### android-build-ascii.ps1 使用方法

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\android-build-ascii.ps1
```

脚本会：

1. 检查 `C:\Users\LittleTaro\codex-bilibili-monitor-ascii` 是否存在。
2. 不存在时创建 junction，指向正式项目目录。
3. 在 ASCII 路径下进入 `android/`。
4. 执行 `.\gradlew.bat test`。
5. 执行 `.\gradlew.bat assembleDebug`。
6. 复制 APK 到 `releases/android/v0.4.0/`。
7. 生成 `build-info.txt`、`changelog.md`、`test-report.md`。

创建 junction 不需要管理员权限；如果本机策略阻止 junction 创建，可以手动把项目复制到纯英文路径构建，但要注意不要把复制目录当成正式工作目录提交。

### Gradle Sync 失败排查

1. 优先从 `android/` 打开工程。
2. 确认使用 `android/gradlew.bat`。
3. 确认 `android/local.properties` 指向本机 SDK。
4. 如果路径包含中文，先用 `scripts/android-build-ascii.ps1` 验证命令行构建是否正常。

### APK 构建失败排查

1. 先运行 `powershell -ExecutionPolicy Bypass -File .\scripts\android-build-ascii.ps1`。
2. 查看 Gradle 输出中第一个失败任务。
3. 检查 `android/app/build/reports/`。
4. 构建失败时不要创建版本 tag。

### 真机安装失败排查

1. 确认 APK 文件名带版本号。
2. 确认手机 Android 版本满足 minSdk 26。
3. 使用 `adb install -r` 复测并记录错误。
4. 不要临时改签名密钥或提交签名材料。

### 导出文件找不到排查

1. v0.4.0 导出成功后会显示文件名、时间和绝对路径。
2. 导出目录仍是 app external files 下的 `exports`，不请求高风险存储权限。
3. 如果文件管理器不可见，v0.4.1 应考虑系统分享或 SAF 文件选择器导出。

### 网络 403 / 412 / 风控限制排查

1. 403 表示访问被拒绝或平台限制。
2. 412 表示请求被风控限制。
3. 登录、验证码、风控场景只记录失败，不绕过、不加 Cookie、不用代理池。
4. 失败快照会保留，便于历史页看到失败时间点。

### Room 数据异常排查

1. v0.4.0 未改 Room schema，数据库版本仍为 1。
2. 同一 BV 使用 `bvId` 主键，不会重复创建 video 记录。
3. 每次手动刷新会追加 snapshot。
4. 历史记录按 `collectedAt DESC, id DESC` 排序。
5. 如需改 schema，下一版必须提高 Room version 并补 migration 或明确破坏性迁移策略。

## Android v0.5.0 低频刷新排查

### 自动刷新没有准点执行

1. 先确认设置页显示“已开启”。
2. 确认间隔是 15 分钟、30 分钟、1 小时、3 小时或 6 小时之一。
3. 查看日志页是否有 `auto refresh registered`、`auto refresh worker started`、`auto refresh worker finished`。
4. WorkManager 周期任务可能被 Android 省电策略延迟或合并；这不是实时监控能力。
5. 如果手机厂商后台限制严格，先关闭电池优化复测，但不要实现隐藏保活。

### 自动刷新请求失败

1. 查看日志页 `auto 刷新请求失败` 和失败快照。
2. 区分无网络、超时、HTTP 403、HTTP 412、登录、验证码、风控。
3. 自动刷新只针对已经添加的视频；没有添加视频时应只有批量开始/完成日志。
4. 遇到登录、验证码或风控只记录失败，不加 Cookie、不代理、不绕过。

### 设置不生效

1. 设置项保存在 DataStore，不写入 Room。
2. 切换开启/关闭后应有注册或取消日志。
3. 修改间隔或 Wi-Fi 约束时，如果自动刷新已开启，应有重调度日志。
4. 清理应用数据会清除 DataStore 设置和 Room 数据。

### 分享导出失败

1. 先确认导出页已经生成 JSON 或 CSV，并显示文件名、大小、时间和绝对路径。
2. 分享使用 FileProvider，只开放 app external files 下 `exports/`。
3. 不需要也不应申请 `MANAGE_EXTERNAL_STORAGE` 或宽泛外部存储权限。
4. 如果目标 App 收不到文件，换一个系统分享目标复测并记录设备型号。

### 趋势图异常

1. 趋势只使用本地 Room 快照，不发起网络请求。
2. 空数据应显示空状态；单点数据只画点，不强行画线。
3. 指标字段为 null 时跳过该绘图点，表格中显示 `-`。
4. 最近 20/50 只影响趋势计算窗口，不删除历史快照。

## Android v0.5.1 设置页与自动刷新热修复排查

### 设置页不可见排查路径

1. 先看首页是否有“自动刷新设置”按钮。
2. 再看顶部导航是否可以横向滑动，并能看到“设置”按钮。
3. 如果横屏可见、竖屏不可见，优先检查导航是否仍是普通 `Row` 而不是可滚动导航。
4. 检查 `MonitorApp.kt` 中 `Page.Settings` 是否在 `when (page)` 中注册。
5. 检查 `SettingsPage()` 是否没有被 `selectedBvId` 条件拦截；设置页不应要求先选视频。

### Compose Navigation 排查路径

1. 当前 MVP 未使用 Navigation Compose route，而是用 `Page` enum 和 `when` 分支。
2. 导航入口必须调用 `onSelect(Page.Settings)`。
3. 顶部导航按钮过多时必须可滚动或换行，不能依赖最后一个按钮刚好在屏幕内。
4. 首页必须保留一个明确设置入口，避免用户只能从顶部导航猜测。

### WorkManager 未注册排查路径

1. 设置页开启自动刷新后，应显示 `WorkManager 注册：已注册，等待系统调度`。
2. 日志页应出现 `auto refresh registered`。
3. DataStore 中 `workRegistered` 应为 true。
4. 如果没有注册状态，检查设置开关回调是否调用 `AutoRefreshRegistrationController.changeEnabled(true, ...)`。
5. 检查 `AutoRefreshScheduler.schedule()` 是否调用 `enqueueUniquePeriodicWork()`。

### WorkManager 已注册但不执行排查路径

1. WorkManager 周期任务不保证准点执行，15 分钟只是最小周期。
2. 设置页如果只有最近注册时间，没有最近开始时间，说明任务可能仍在等待系统调度。
3. 仅 Wi-Fi 开启时，移动网络不会满足 `UNMETERED` 约束。
4. 电量低或厂商后台限制可能推迟任务。
5. 不要用高频循环、隐藏保活或前台规避来制造执行。

### 自动刷新无日志排查路径

1. 开启/关闭设置应立即写入注册/取消日志。
2. Worker 开始执行时应写入 `auto refresh worker started`。
3. Worker 完成时应写入 `auto refresh worker finished`。
4. Worker 失败时应写入 `auto refresh worker failed`，且设置页显示最近错误。
5. 如果设置页显示已注册但日志没有注册记录，检查 Repository `writeLog()` 调用。

### DataStore 设置未生效排查路径

1. 设置页状态来自 `AutoRefreshSettingsStore.settings` Flow。
2. 切换开关后应同时调用 `setEnabled()` 和记录注册/取消时间。
3. 修改间隔或 Wi-Fi 约束后，如果已开启，应重新注册 WorkManager 并记录新的注册时间。
4. 清理应用数据会清空 DataStore 和 Room，这是预期行为。

### 实机判断自动刷新是否有效的方法

1. 进入首页，点击“自动刷新设置”。
2. 开启自动刷新，确认设置页显示“已注册，等待系统调度”。
3. 打开日志页，确认有 `auto refresh registered`。
4. 等待 Android 系统调度后，设置页应出现最近开始/结束时间。
5. 如果已有视频，历史页应追加成功快照或失败快照。
6. 断网测试时，自动刷新失败应写失败快照或错误日志，不应静默失败。

## Android v0.6.0 自动刷新诊断增强排查

### 诊断区不显示

1. 进入首页点击“自动刷新设置”。
2. 设置页应显示任务名称、开关、注册、间隔、网络约束、最近状态和累计成功/失败。
3. 如果没有累计计数，检查 `AutoRefreshSettingsStore` 是否读取 `auto_refresh_success_count` 和 `auto_refresh_failure_count`。

### 测试自动刷新一次失败

1. 按钮只执行一次，不循环。
2. 查看设置页最近结果和最近错误。
3. 查看日志页 `manual auto refresh test started/finished/failed`。
4. 如果断网，失败应记录为错误或 failed snapshot，不应静默。

### 批量刷新所有视频失败

1. 按钮只刷新本地已添加视频。
2. 没有视频时应显示 `total=0, success=0, failed=0`。
3. 单个视频失败不应阻断其它视频刷新；结果应统计 failed。

### 日志筛选异常

1. 先切回“全部”确认日志总量。
2. level 筛选按 `info` / `warning` / `error` 匹配。
3. 自动刷新筛选按 `auto` 关键词匹配 message/detail。
4. 手动刷新筛选按 `manual` 关键词匹配 message/detail。
5. 导出筛选按 tag `export` 匹配。

## Android v0.7.0 导航、导出和设置页排查

### 顶部导航显示异常

1. 未选中视频时，顶部导航只应显示“首页 / 设置 / 高级”。
2. 选中首页列表中的视频后，顶部导航才应显示“详情 / 历史”。
3. 如果删除或清空了当前选中视频，详情和历史入口应消失，页面应回到首页。
4. 如果“设置”被错误高亮，检查当前 `Page` 状态和 `pageLabel(page)`，不要写死设置页选中态。
5. 旋转屏幕后选中视频应通过 `rememberSaveable` 保留；App 被系统杀掉后的长期恢复不属于当前版本范围。

### 状态栏或刘海屏遮挡

1. App 根容器应使用 `safeDrawingPadding()`。
2. 不要给顶部导航再叠加固定高度状态栏 padding，避免双重留白。
3. 如果某个页面单独贴边，优先检查该页面是否绕过了 `MonitorApp` 根容器。

### 首次导出没有系统保存窗口

1. 默认设置应为 `askExportLocationEveryTime=true` 且 `defaultExportTreeUri=null`。
2. 直接导出 JSON/CSV 时应调用 `CreateDocument`，由系统保存窗口选择文件名和位置。
3. 不能先写到 app 外部目录再把路径展示给用户；分享功能可以继续使用 app 私有导出文件。

### 默认导出目录不生效

1. `CreateDocument` 返回的是文件 URI，不能把它当目录 URI。
2. 默认目录必须通过 `OpenDocumentTree` 获取，并调用 `takePersistableUriPermission()`。
3. 直存前必须检查 `contentResolver.persistedUriPermissions` 是否仍有写权限。
4. 授权失效时应清除默认目录并回退系统保存窗口，而不是静默失败。
5. 同名文件应追加后缀，避免覆盖已有导出文件。

### Android unit test 在中文路径下 ClassNotFoundException

1. 如果 `app/build/intermediates/javac/.../*Test.class` 存在，但测试报告显示所有测试类 `ClassNotFoundException`，优先怀疑 Gradle/JDK worker classpath 在中文路径下异常。
2. 使用 `C:\Users\LittleTaro\codex-bilibili-monitor-ascii\android` 这个 ASCII junction 重新执行同一测试。
3. 只有 ASCII 路径下仍失败时，才按代码或测试逻辑失败处理。

## Android v0.8.0 高级页和滚动布局排查

### 高级页闪退

1. 优先检查是否存在 `LazyColumn` 内再渲染另一个无固定高度 `LazyColumn`。
2. v0.7.0 的风险点是 `AdvancedPage` 外层 `LazyColumn` 的 item 中调用 `LogsPage()`，而 `LogsPage()` 在有日志时又创建竖向 `LazyColumn`。
3. Compose 典型异常是竖向可滚动组件在无限高度约束下被测量，不能用 try/catch 静默吞掉。
4. 修复方式是让高级页只有一个主滚动列表：标题、导出、日志筛选、日志卡片全部作为同一个 `LazyColumn` 的 item。
5. 首页、详情、历史、设置同样应避免无界父布局中嵌套竖向滚动列表。

### 最近快照底部不可见

1. 详情页必须是可纵向滚动页面，不要用固定 `Column` 承载所有快照字段。
2. 根布局中页面内容区需要有明确高度约束，例如在导航下方使用 `weight(1f)`。
3. 页面底部只保留少量内容内边距，不要叠加根安全区和页面安全区造成大空白。
4. 字体放大时，最近快照字段应继续通过页面滚动查看，而不是被底部系统区域遮住。

### 自动刷新短间隔

1. UI 允许选择 1m、3m、5m、10m、15m、30m、1h、2h。
2. WorkManager 周期任务不能承诺低于 Android 最小 15 分钟的后台稳定周期。
3. `RefreshIntervals.backgroundScheduleMinutes()` 应把低于 15m 的选择映射到 15m 后台有效周期。
4. 日志和状态提示应同时记录 selected interval 和 effective interval。

### 折叠内容回归

1. 长标题、错误详情、日志详情和诊断区可以折叠。
2. 操作按钮不能因为折叠而默认隐藏。
3. 折叠状态使用 `rememberSaveable`，普通重组不应丢失。
4. 动画仅使用轻量 `animateContentSize` / `AnimatedVisibility`，不要阻塞滚动和点击。
