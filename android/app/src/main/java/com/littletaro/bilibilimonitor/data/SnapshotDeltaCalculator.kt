package com.littletaro.bilibilimonitor.data

object SnapshotDeltaCalculator {
    /** Null means that this field cannot be compared (first record or missing value). */
    fun delta(current: Long?, previous: Long?): Long? =
        if (current != null && previous != null) current - previous else null
}
