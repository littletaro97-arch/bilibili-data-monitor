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
