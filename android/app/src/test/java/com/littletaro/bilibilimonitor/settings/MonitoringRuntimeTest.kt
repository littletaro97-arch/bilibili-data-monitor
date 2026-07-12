package com.littletaro.bilibilimonitor.settings

import java.time.Instant
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MonitoringRuntimeTest {
    @Test fun mapsIntervalsToActualModes() {
        assertEquals(ScheduleModes.OFF, MonitoringRuntime.mode(AutoRefreshSettings(enabled = false, intervalMinutes = 5)))
        assertEquals(ScheduleModes.FOREGROUND, MonitoringRuntime.mode(AutoRefreshSettings(enabled = true, intervalMinutes = 5)))
        assertEquals(ScheduleModes.CONTINUOUS, MonitoringRuntime.mode(AutoRefreshSettings(enabled = true, intervalMinutes = 5, continuousMonitoringEnabled = true)))
        assertEquals(ScheduleModes.WORK_MANAGER, MonitoringRuntime.mode(AutoRefreshSettings(enabled = true, intervalMinutes = 30)))
        assertEquals(3L, MonitoringRuntime.effectiveInterval(AutoRefreshSettings(enabled = true, intervalMinutes = 3)))
        assertEquals(15L, MonitoringRuntime.effectiveInterval(AutoRefreshSettings(enabled = true, intervalMinutes = 15)))
        assertEquals(5L, MonitoringRuntime.effectiveInterval(AutoRefreshSettings(enabled = true, intervalMinutes = 5, continuousMonitoringEnabled = true)))
        assertEquals(60L, MonitoringRuntime.effectiveInterval(AutoRefreshSettings(enabled = true, intervalMinutes = 60)))
    }

    @Test fun countdownUsesPersistedAbsoluteNextTimeAndClampsProgress() {
        val settings = AutoRefreshSettings(
            enabled = true,
            intervalMinutes = 5,
            effectiveIntervalMinutes = 5,
            scheduleMode = ScheduleModes.CONTINUOUS,
            nextScheduledCheckAt = "2026-07-12T00:05:00Z",
            checkState = CheckStates.WAITING
        )
        val middle = MonitoringRuntime.countdown(settings, Instant.parse("2026-07-12T00:02:00Z"))
        assertEquals(180L, middle.remainingSeconds)
        assertEquals(0.4f, middle.progress!!, 0.001f)
        val expired = MonitoringRuntime.countdown(settings, Instant.parse("2026-07-12T01:00:00Z"))
        assertEquals(0L, expired.remainingSeconds)
        assertEquals(1f, expired.progress!!, 0.001f)
    }

    @Test fun disabledRunningAndFailedDoNotShowFakeProgress() {
        assertNull(MonitoringRuntime.countdown(AutoRefreshSettings(), Instant.EPOCH).progress)
        assertNull(MonitoringRuntime.countdown(AutoRefreshSettings(enabled = true, checkState = CheckStates.RUNNING), Instant.EPOCH).progress)
        val failed = AutoRefreshSettings(enabled = true, checkState = CheckStates.FAILED, lastAutoRefreshError = "network")
        assertTrue(MonitoringRuntime.countdown(failed, Instant.EPOCH).headline.contains("失败"))
    }
}
