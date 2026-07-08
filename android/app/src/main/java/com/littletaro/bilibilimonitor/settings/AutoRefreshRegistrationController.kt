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
            AutoRefreshRegistrationResult("registered", "已注册自动刷新，等待 Android 系统调度")
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
            AutoRefreshRegistrationResult("registered", "已按新间隔重新注册自动刷新")
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
            AutoRefreshRegistrationResult("registered", "已更新网络约束并重新注册自动刷新")
        } else {
            AutoRefreshRegistrationResult("saved", "已保存网络约束")
        }
    }
}
