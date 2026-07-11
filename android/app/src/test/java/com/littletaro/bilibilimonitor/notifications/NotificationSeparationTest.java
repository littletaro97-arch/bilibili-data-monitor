package com.littletaro.bilibilimonitor.notifications;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

import com.littletaro.bilibilimonitor.worker.ContinuousMonitoringService;
import org.junit.Test;

public class NotificationSeparationTest {
    @Test
    public void backgroundAndResultNotificationsHaveIndependentBehavior() {
        assertNotEquals(ContinuousMonitoringService.CHANNEL_ID, MonitorNotificationManager.RESULT_CHANNEL_ID);
        assertTrue(ContinuousMonitoringService.NOTIFICATION_ONGOING);
        assertFalse(ContinuousMonitoringService.NOTIFICATION_AUTO_CANCEL);
        assertFalse(MonitorNotificationManager.RESULT_NOTIFICATION_ONGOING);
        assertTrue(MonitorNotificationManager.RESULT_NOTIFICATION_AUTO_CANCEL);
    }
}
