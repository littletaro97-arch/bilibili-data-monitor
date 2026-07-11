package com.littletaro.bilibilimonitor.data;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import java.time.Instant;
import org.junit.Test;

public class DeviceTimeTest {
    @Test
    public void nowIsoStringUsesCanonicalUtcFormat() {
        String value = DeviceTime.nowIsoString();

        assertNotNull(Instant.parse(value));
        assertTrue(value.endsWith("Z"));
    }

    @Test
    public void displayFormatterConvertsUtcAndOffsetInputs() {
        assertTrue(DeviceTime.formatForDisplay("2026-07-11T00:00:00Z").contains("2026"));
        assertTrue(DeviceTime.formatForDisplay("2026-07-11T09:00:00+09:00").contains("2026"));
    }

    @Test
    public void comparesEquivalentOffsetsAsSameAbsoluteTime() {
        assertTrue(DeviceTime.compareAbsolute("2026-07-12T09:00:00+09:00", "2026-07-12T00:00:00Z") == 0);
        assertTrue(DeviceTime.compareAbsolute("2026-07-12T00:00:01Z", "2026-07-12T09:00:00+09:00") > 0);
    }
}
