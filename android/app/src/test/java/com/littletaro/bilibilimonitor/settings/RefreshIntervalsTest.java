package com.littletaro.bilibilimonitor.settings;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class RefreshIntervalsTest {
    @Test
    public void defaultAutoRefreshIsOff() {
        AutoRefreshSettings settings = new AutoRefreshSettings();

        assertFalse(settings.getEnabled());
        assertEquals(60L, settings.getIntervalMinutes());
        assertTrue(settings.getWifiOnly());
    }

    @Test
    public void intervalValidationOnlyAllowsLowFrequencyValues() {
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(15L));
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(30L));
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(60L));
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(180L));
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(360L));
        assertFalse(RefreshIntervals.INSTANCE.isAllowed(5L));
        assertFalse(RefreshIntervals.INSTANCE.isAllowed(10L));
    }

    @Test
    public void unsupportedIntervalFallsBackToDefault() {
        assertEquals(60L, RefreshIntervals.INSTANCE.sanitize(5L));
        assertEquals(30L, RefreshIntervals.INSTANCE.sanitize(30L));
    }
}
