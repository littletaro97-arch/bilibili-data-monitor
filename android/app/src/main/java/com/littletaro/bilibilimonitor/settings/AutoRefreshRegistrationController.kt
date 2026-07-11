package com.littletaro.bilibilimonitor.settings

interface AutoRefreshRegistrationClient {
    fun schedule(intervalMinutes: Long, wifiOnly: Boolean)
    fun cancel()
}

data class AutoRefreshRegistrationResult(
    val action: String,
    val message: String
)

object AutoRefreshRegistrationController {
    fun changeEnabled(
        enabled: Boolean,
        settings: AutoRefreshSettings,
        client: AutoRefreshRegistrationClient
    ): AutoRefreshRegistrationResult {
        return if (enabled) {
            client.schedule(settings.intervalMinutes, settings.wifiOnly)
            AutoRefreshRegistrationResult(
                "registered",
                registrationMessage(settings.intervalMinutes)
            )
        } else {
            client.cancel()
            AutoRefreshRegistrationResult("cancelled", "已取消自动刷新")
        }
    }

    fun changeInterval(
        minutes: Long,
        settings: AutoRefreshSettings,
        client: AutoRefreshRegistrationClient
    ): AutoRefreshRegistrationResult {
        require(RefreshIntervals.isAllowed(minutes)) { "Unsupported interval: $minutes" }
        return if (settings.enabled) {
            client.schedule(minutes, settings.wifiOnly)
            AutoRefreshRegistrationResult("registered", registrationMessage(minutes))
        } else {
            AutoRefreshRegistrationResult("saved", "已保存间隔")
        }
    }

    fun changeWifiOnly(
        wifiOnly: Boolean,
        settings: AutoRefreshSettings,
        client: AutoRefreshRegistrationClient
    ): AutoRefreshRegistrationResult {
        return if (settings.enabled) {
            client.schedule(settings.intervalMinutes, wifiOnly)
            AutoRefreshRegistrationResult("registered", registrationMessage(settings.intervalMinutes))
        } else {
            AutoRefreshRegistrationResult("saved", "已保存网络约束")
        }
    }

    private fun registrationMessage(minutes: Long): String {
        val effective = RefreshIntervals.backgroundScheduleMinutes(minutes)
        return if (effective == minutes) {
            "已注册自动刷新，等待 Android 系统调度"
        } else {
            "已保存 ${minutes}m；后台任务按 Android 最小 ${effective}m 调度"
        }
    }
}
