package com.littletaro.bilibilimonitor.data;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class SnapshotSourcesTest {
    @Test
    public void triggerMapsToPersistedSource() {
        assertEquals(SnapshotSources.MANUAL, SnapshotSources.INSTANCE.from(RefreshTrigger.MANUAL));
        assertEquals(SnapshotSources.AUTO, SnapshotSources.INSTANCE.from(RefreshTrigger.AUTO));
    }

    @Test
    public void oldRowsHaveExplicitUnknownValue() {
        assertEquals("UNKNOWN", SnapshotSources.UNKNOWN);
    }
}
