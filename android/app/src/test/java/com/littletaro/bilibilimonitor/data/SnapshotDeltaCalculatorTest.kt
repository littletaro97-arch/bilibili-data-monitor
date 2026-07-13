package com.littletaro.bilibilimonitor.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class SnapshotDeltaCalculatorTest {
    @Test fun calculatesPositiveNegativeAndZeroChanges() {
        assertEquals(320L, SnapshotDeltaCalculator.delta(12_430, 12_110))
        assertEquals(-2L, SnapshotDeltaCalculator.delta(104, 106))
        assertEquals(0L, SnapshotDeltaCalculator.delta(76, 76))
    }

    @Test fun firstOrMissingRecordIsNotReportedAsZero() {
        assertNull(SnapshotDeltaCalculator.delta(100, null))
        assertNull(SnapshotDeltaCalculator.delta(null, 100))
    }
}
