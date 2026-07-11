package com.littletaro.bilibilimonitor.settings;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class NotificationIntervalsTest {
    @Test
    public void notificationIntervalCannotBeShorterThanEffectiveDetectionInterval() {
        assertEquals(15L, NotificationIntervals.sanitize(5L, 1L));
        assertEquals(30L, NotificationIntervals.sanitize(5L, 30L));
        assertEquals(60L, NotificationIntervals.sanitize(55L, 60L));
    }

    @Test
    public void notificationIntervalRoundsUpToFiveMinuteStep() {
        assertEquals(20L, NotificationIntervals.sanitize(16L, 15L));
        assertEquals(65L, NotificationIntervals.sanitize(61L, 60L));
    }

    @Test
    public void optionsStartAtDetectionLowerBound() {
        assertEquals(15L, (long) NotificationIntervals.options(1L).get(0));
        assertEquals(30L, (long) NotificationIntervals.options(30L).get(0));
        assertTrue(NotificationIntervals.options(60L).contains(120L));
    }
}
