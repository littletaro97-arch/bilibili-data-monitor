package com.littletaro.bilibilimonitor.settings;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class AutoRefreshRegistrationControllerTest {
    @Test
    public void enablingAutoRefreshCallsSchedule() {
        FakeClient client = new FakeClient();
        AutoRefreshSettings settings = new AutoRefreshSettings(
                false,
                30L,
                false,
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
                "csv"
        );

        AutoRefreshRegistrationResult result =
                AutoRefreshRegistrationController.INSTANCE.changeEnabled(true, settings, client);

        assertEquals("registered", result.getAction());
        assertEquals(1, client.scheduleCalls);
        assertEquals(30L, client.lastInterval);
        assertFalse(client.lastWifiOnly);
        assertEquals(0, client.cancelCalls);
    }

    @Test
    public void disablingAutoRefreshCallsCancel() {
        FakeClient client = new FakeClient();

        AutoRefreshRegistrationResult result =
                AutoRefreshRegistrationController.INSTANCE.changeEnabled(false, new AutoRefreshSettings(), client);

        assertEquals("cancelled", result.getAction());
        assertEquals(0, client.scheduleCalls);
        assertEquals(1, client.cancelCalls);
    }

    @Test
    public void changingIntervalOnlyReschedulesWhenEnabled() {
        FakeClient client = new FakeClient();
        AutoRefreshSettings enabled = new AutoRefreshSettings(
                true,
                60L,
                true,
                true,
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
                "csv"
        );

        AutoRefreshRegistrationResult enabledResult =
                AutoRefreshRegistrationController.INSTANCE.changeInterval(15L, enabled, client);

        assertEquals("registered", enabledResult.getAction());
        assertEquals(1, client.scheduleCalls);
        assertEquals(15L, client.lastInterval);
        assertTrue(client.lastWifiOnly);

        FakeClient disabledClient = new FakeClient();
        AutoRefreshRegistrationResult disabledResult =
                AutoRefreshRegistrationController.INSTANCE.changeInterval(30L, new AutoRefreshSettings(), disabledClient);

        assertEquals("saved", disabledResult.getAction());
        assertEquals(0, disabledClient.scheduleCalls);
    }

    @Test
    public void shortIntervalKeepsSingleUniqueRegistrationRequestAndReportsEffectiveBackgroundMinimum() {
        FakeClient client = new FakeClient();
        AutoRefreshSettings enabled = new AutoRefreshSettings(
                true,
                60L,
                true,
                true,
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
                "csv"
        );

        AutoRefreshRegistrationResult result =
                AutoRefreshRegistrationController.INSTANCE.changeInterval(1L, enabled, client);

        assertEquals("registered", result.getAction());
        assertEquals(1, client.scheduleCalls);
        assertEquals(1L, client.lastInterval);
        assertTrue(result.getMessage().contains("15m"));
    }

    @Test
    public void changingWifiOnlyOnlyReschedulesWhenEnabled() {
        FakeClient client = new FakeClient();
        AutoRefreshSettings enabled = new AutoRefreshSettings(
                true,
                120L,
                true,
                true,
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
                "csv"
        );

        AutoRefreshRegistrationController.INSTANCE.changeWifiOnly(false, enabled, client);

        assertEquals(1, client.scheduleCalls);
        assertEquals(120L, client.lastInterval);
        assertFalse(client.lastWifiOnly);

        FakeClient disabledClient = new FakeClient();
        AutoRefreshRegistrationController.INSTANCE.changeWifiOnly(false, new AutoRefreshSettings(), disabledClient);

        assertEquals(0, disabledClient.scheduleCalls);
    }

    private static class FakeClient implements AutoRefreshRegistrationClient {
        int scheduleCalls = 0;
        int cancelCalls = 0;
        long lastInterval = -1L;
        boolean lastWifiOnly = true;

        @Override
        public void schedule(long intervalMinutes, boolean wifiOnly) {
            scheduleCalls++;
            lastInterval = intervalMinutes;
            lastWifiOnly = wifiOnly;
        }

        @Override
        public void cancel() {
            cancelCalls++;
        }
    }
}
