package com.littletaro.bilibilimonitor.notifications

import com.littletaro.bilibilimonitor.data.RefreshAllResult
import com.littletaro.bilibilimonitor.settings.AutoRefreshSettings
import com.littletaro.bilibilimonitor.settings.NotificationModes
import java.time.Duration
import java.time.Instant

object MonitorNotificationPolicy {
    @JvmStatic
    fun shouldSend(
        settings: AutoRefreshSettings,
        permissionGranted: Boolean,
        now: Instant
    ): Boolean {
        if (!settings.notificationsEnabled || !permissionGranted) return false
        if (settings.notificationMode == NotificationModes.EACH_REFRESH) return true
        val lastSentAt = settings.lastNotificationSentAt?.let { runCatching { Instant.parse(it) }.getOrNull() }
            ?: return true
        val elapsedMinutes = Duration.between(lastSentAt, now).toMinutes()
        return elapsedMinutes >= settings.notificationIntervalMinutes
    }

    @JvmStatic
    fun title(result: RefreshAllResult): String =
        if (result.failed == 0) "B站监控检测完成" else "B站监控检测有失败"

    @JvmStatic
    fun body(result: RefreshAllResult): String {
        if (result.total == 0) return "没有可检测的视频，未发送空提醒"
        val state = if (result.failed == 0) "成功" else "部分失败"
        val changeHint = if (result.success > 0) "已记录最新快照" else "未记录新快照"
        return "对象 ${result.total} 个，$state ${result.success} 个，失败 ${result.failed} 个；$changeHint"
    }
}
