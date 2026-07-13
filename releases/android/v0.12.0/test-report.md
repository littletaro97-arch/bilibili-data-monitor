# v0.12.0 Android test report

## Automated build

- `clean test lintDebug assembleDebug assembleRelease assembleDebugAndroidTest --no-daemon --stacktrace`: passed through the ASCII junction.
- Release packaging script: `powershell -ExecutionPolicy Bypass -File .\android\scripts\build-ascii.ps1 -Version v0.12.0`: passed.
- Debug JVM unit tests: 82 passed, 0 failed, 0 errors, 0 skipped.
- Debug lint, Debug APK, unsigned Release APK, and androidTest APK compilation: passed.
- Windows compatibility tests: `python -m pytest` passed, 56 passed.

## Added automated coverage

- 20 / 50 / 全部范围、首尾点、峰值、突变、同步多序列降采样和 5,000 条压力数据。
- 比值计算、零分母、缺失值、分子/分母时间对齐。
- 最近快照正、负、零变化和首次/缺失值不伪造零变化。
- view API `data.pic` 封面解析、HTTPS B站 CDN URL 策略、Android/Windows 可选封面交换。
- Room v2→v4 迁移结构和旧快照绝对时间毫秒回填（androidTest 已编译）。

## Pressure measurement

- JVM sampled-data transformation, not device rendering: 100 raw → 100 displayed in 20.4196 ms; 500 raw → 180 displayed in 13.5738 ms; 5,000 raw → 180 displayed in 24.6483 ms.
- Sampling uses time buckets and retains each bucket's first/last plus extrema candidates. The current 360-point test budget yielded 180 points for monotonic test data; no original database records were altered.
- Room query latency, memory profiler data, Canvas frame time, scrolling frame time and image-cache residency were not measured on an Android runtime. Do not interpret this report as a 60 FPS claim.

## Not executed

- No `adb` and no Android emulator executable/AVD are available in this environment. Compose UI tests, Room migration runtime, image download/cache runtime and simulator interaction were not run.
- No physical device was connected or tested. The manual checklist is `real-device-checklist.md` in this release directory.
