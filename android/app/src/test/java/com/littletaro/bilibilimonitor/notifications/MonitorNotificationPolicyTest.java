package com.littletaro.bilibilimonitor.notifications;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.littletaro.bilibilimonitor.settings.AutoRefreshSettings;
import com.littletaro.bilibilimonitor.settings.NotificationModes;
import java.time.Instant;
import org.junit.Test;

public class MonitorNotificationPolicyTest {
    @Test
    public void disabledOrMissingPermissionNeverSends() {
        AutoRefreshSettings enabled = settings(true, NotificationModes.EACH_REFRESH, 60L, null);

        assertFalse(MonitorNotificationPolicy.shouldSend(enabled, false, Instant.parse("2026-07-11T00:00:00Z")));
        assertFalse(MonitorNotificationPolicy.shouldSend(settings(false, NotificationModes.EACH_REFRESH, 60L, null), true, Instant.parse("2026-07-11T00:00:00Z")));
    }

    @Test
    public void eachRefreshModeSendsForEveryCompletedRun() {
        AutoRefreshSettings enabled = settings(true, NotificationModes.EACH_REFRESH, 60L, "2026-07-11T00:00:00Z");

        assertTrue(MonitorNotificationPolicy.shouldSend(enabled, true, Instant.parse("2026-07-11T00:01:00Z")));
    }

    @Test
    public void summaryModeDeduplicatesInsideConfiguredWindow() {
        AutoRefreshSettings enabled = settings(true, NotificationModes.SUMMARY, 30L, "2026-07-11T00:00:00Z");

        assertFalse(MonitorNotificationPolicy.shouldSend(enabled, true, Instant.parse("2026-07-11T00:20:00Z")));
        assertTrue(MonitorNotificationPolicy.shouldSend(enabled, true, Instant.parse("2026-07-11T00:30:00Z")));
    }

    @Test
    public void summaryModeAcceptsLocalOffsetStoredTime() {
        AutoRefreshSettings enabled = settings(true, NotificationModes.SUMMARY, 30L, "2026-07-11T09:00:00+09:00");

        assertFalse(MonitorNotificationPolicy.shouldSend(enabled, true, Instant.parse("2026-07-11T00:20:00Z")));
        assertTrue(MonitorNotificationPolicy.shouldSend(enabled, true, Instant.parse("2026-07-11T00:30:00Z")));
    }

    private AutoRefreshSettings settings(
            boolean notificationsEnabled,
            String mode,
            long notificationIntervalMinutes,
            String lastNotificationSentAt
    ) {
        return new AutoRefreshSettings(
                false,
                60L,
                true,
                false,
                null,
                null,
                null,
                null,
                null,
                null,
                0L,
                0L,
                null,
                true,
                "csv",
                notificationsEnabled,
                true,
                mode,
                notificationIntervalMinutes,
                lastNotificationSentAt,
                true
        );
    }
}
