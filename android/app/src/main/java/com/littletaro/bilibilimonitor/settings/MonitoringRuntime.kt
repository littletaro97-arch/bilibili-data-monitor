package com.littletaro.bilibilimonitor.settings

import com.littletaro.bilibilimonitor.data.DeviceTime
import java.time.Duration
import java.time.Instant

data class CountdownState(
    val headline: String,
    val remainingSeconds: Long?,
    val progress: Float?,
    val nextLabel: String
)

object MonitoringRuntime {
    fun mode(settings: AutoRefreshSettings): String = when {
        !settings.enabled -> ScheduleModes.OFF
        settings.continuousMonitoringEnabled && settings.intervalMinutes < RefreshIntervals.MIN_WORK_MANAGER_MINUTES -> ScheduleModes.CONTINUOUS
        settings.intervalMinutes < RefreshIntervals.MIN_WORK_MANAGER_MINUTES -> ScheduleModes.FOREGROUND
        else -> ScheduleModes.WORK_MANAGER
    }

    fun effectiveInterval(settings: AutoRefreshSettings): Long = when (mode(settings)) {
        ScheduleModes.FOREGROUND, ScheduleModes.CONTINUOUS -> settings.intervalMinutes
        ScheduleModes.WORK_MANAGER -> RefreshIntervals.backgroundScheduleMinutes(settings.intervalMinutes)
        else -> settings.intervalMinutes
    }

    fun nextAt(now: Instant, intervalMinutes: Long): String =
        now.plus(Duration.ofMinutes(intervalMinutes)).toString()

    fun countdown(settings: AutoRefreshSettings, now: Instant): CountdownState {
        if (!settings.enabled) {
            return CountdownState("自动检查未开启", null, null, "-")
        }
        if (settings.checkState == CheckStates.RUNNING) {
            return CountdownState("正在检查…", null, null, "检查完成后重新计时")
        }
        if (settings.checkState == CheckStates.FAILED) {
            return CountdownState("上次检查失败", null, null, settings.lastAutoRefreshError ?: "等待重试")
        }
        if (settings.scheduleMode == ScheduleModes.OFF) {
            return CountdownState("等待调度状态同步", null, null, "请稍后或检查设置")
        }
        val next = DeviceTime.parseToInstant(settings.nextScheduledCheckAt)
            ?: return CountdownState("等待系统调度", null, null, "尚无预计时间")
        val totalSeconds = (settings.effectiveIntervalMinutes * 60L).coerceAtLeast(1L)
        val remaining = Duration.between(now, next).seconds.coerceIn(0L, totalSeconds)
        val progress = ((totalSeconds - remaining).toFloat() / totalSeconds.toFloat()).coerceIn(0f, 1f)
        val prefix = if (settings.scheduleMode == ScheduleModes.WORK_MANAGER) "预计" else "下次检查"
        return CountdownState(
            headline = "距离下次检查还有 ${formatDuration(remaining)}",
            remainingSeconds = remaining,
            progress = progress,
            nextLabel = "$prefix：${DeviceTime.formatForDisplay(next.toString())}"
        )
    }

    fun modeLabel(mode: String): String = when (mode) {
        ScheduleModes.CONTINUOUS -> "持续监控"
        ScheduleModes.FOREGROUND -> "仅前台"
        ScheduleModes.WORK_MANAGER -> "后台调度"
        else -> "未开启"
    }

    private fun formatDuration(seconds: Long): String =
        "%02d:%02d".format(seconds / 60, seconds % 60)
}
