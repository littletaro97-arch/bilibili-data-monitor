package com.littletaro.bilibilimonitor.settings

import com.littletaro.bilibilimonitor.data.TrendMetric
import com.littletaro.bilibilimonitor.data.TrendRange
import org.junit.Assert.assertEquals
import org.junit.Test

class ChartPreferencesCodecTest {
    @Test
    fun `round trip retains each video chart selection`() {
        val saved = ChartPreferences(
            displayMode = ChartDisplayMode.Ratio,
            singleMetric = TrendMetric.COIN,
            numeratorMetric = TrendMetric.REPLY,
            denominatorMetric = TrendMetric.VIEW,
            range = TrendRange.ALL
        )

        assertEquals(saved, ChartPreferencesCodec.decode(ChartPreferencesCodec.encode(saved)))
    }

    @Test
    fun `malformed and duplicate ratio metrics fall back to legal defaults`() {
        assertEquals(ChartPreferences(), ChartPreferencesCodec.decode("wrong"))
        assertEquals(
            ChartPreferences(displayMode = ChartDisplayMode.Ratio, numeratorMetric = TrendMetric.LIKE, denominatorMetric = TrendMetric.VIEW, range = TrendRange.ALL),
            ChartPreferencesCodec.decode("Ratio|VIEW|LIKE|LIKE|ALL")
        )
    }
}
