package com.littletaro.bilibilimonitor.worker

import org.junit.Assert.assertEquals
import org.junit.Test

class ContinuousMonitoringConfigurationTest {
    @Test fun notificationTextAlwaysUsesLatestEffectiveInterval() {
        assertEquals("当前间隔：1 分钟；系统可能延迟执行", ContinuousMonitoringService.foregroundNotificationText(1))
        assertEquals("当前间隔：3 分钟；系统可能延迟执行", ContinuousMonitoringService.foregroundNotificationText(3))
    }
}
