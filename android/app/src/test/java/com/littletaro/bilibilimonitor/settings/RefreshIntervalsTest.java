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
    public void intervalValidationOnlyAllowsWheelPickerValues() {
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(1L));
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(3L));
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(5L));
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(10L));
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(15L));
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(30L));
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(60L));
        assertTrue(RefreshIntervals.INSTANCE.isAllowed(120L));
        assertFalse(RefreshIntervals.INSTANCE.isAllowed(2L));
        assertFalse(RefreshIntervals.INSTANCE.isAllowed(180L));
    }

    @Test
    public void unsupportedIntervalFallsBackToDefault() {
        assertEquals(60L, RefreshIntervals.INSTANCE.sanitize(180L));
        assertEquals(30L, RefreshIntervals.INSTANCE.sanitize(30L));
    }

    @Test
    public void shortIntervalsUseWorkManagerMinimumForBackgroundSchedule() {
        assertEquals(15L, RefreshIntervals.INSTANCE.backgroundScheduleMinutes(1L));
        assertEquals(15L, RefreshIntervals.INSTANCE.backgroundScheduleMinutes(10L));
        assertEquals(15L, RefreshIntervals.INSTANCE.backgroundScheduleMinutes(15L));
        assertEquals(30L, RefreshIntervals.INSTANCE.backgroundScheduleMinutes(30L));
        assertEquals(60L, RefreshIntervals.INSTANCE.backgroundScheduleMinutes(999L));
    }
}
