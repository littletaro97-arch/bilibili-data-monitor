# v0.10.0 Test Report

## 已执行

- Windows：`python -m pytest`，47 passed。
- Android：`clean test`，57 passed（包含新增快照来源测试）。
- Android：`lintDebug`，passed。
- Android：`assembleDebug`，passed。
- 静态检查：`git diff --check`，passed。

## 未执行

- Compose instrumentation / UI test：项目当前没有 `androidTest` 测试用例，且本机没有可用 AVD 或连接设备。
- 模拟器安装与启动：Android SDK emulator 存在，但 `emulator -list-avds` 返回空列表。
- 真实系统通知、通知渠道关闭、Android 13+ 权限、B站 App / 浏览器跳转：无设备，未执行。
- 实机、小屏、大字体、横屏、锁屏、厂商后台限制：无设备，未执行。

不得将 JVM 策略测试与 APK 构建结果视为真实系统通知通过。
