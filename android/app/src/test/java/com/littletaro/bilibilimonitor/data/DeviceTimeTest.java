package com.littletaro.bilibilimonitor.data;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import java.time.OffsetDateTime;
import org.junit.Test;

public class DeviceTimeTest {
    @Test
    public void nowIsoStringUsesLocalOffsetDateTimeFormat() {
        String value = DeviceTime.nowIsoString();

        assertNotNull(OffsetDateTime.parse(value));
        assertTrue(value.contains("+") || value.endsWith("Z") || value.substring(10).contains("-"));
    }

    @Test
    public void displayFormatterConvertsUtcAndOffsetInputs() {
        assertTrue(DeviceTime.formatForDisplay("2026-07-11T00:00:00Z").contains("2026"));
        assertTrue(DeviceTime.formatForDisplay("2026-07-11T09:00:00+09:00").contains("2026"));
    }
}
