# v0.11.0 Real-device checklist

- Video open: Bilibili installed, Bilibili disabled/browser fallback, multiple browsers, mobile/short/timestamp links, rapid taps and invalid BV.
- Continuous monitoring: start/stop notification, 1/3/5/10 minutes, screen off, lock screen, background, recent-task removal, process reclaim, reboot, Wi-Fi/mobile/offline and battery optimization.
- Guidance: first enable, skip, `高级 · 后台受限`, diagnostics navigation, warning refresh and manufacturer status `需要确认`.
- Exchange: Android export to Windows, Windows import/export, Android re-import, duplicate, conflict, corrupted ZIP, old data retention, Unicode and source labels.

Expected logs: Android Advanced page and `adb logcat`; WorkManager via `adb shell dumpsys jobscheduler`; foreground service via `adb shell dumpsys activity services com.littletaro.bilibilimonitor`.
