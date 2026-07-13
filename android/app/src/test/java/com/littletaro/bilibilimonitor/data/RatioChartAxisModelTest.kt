package com.littletaro.bilibilimonitor.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RatioChartAxisModelTest {
    @Test
    fun `raw metrics share a left axis and valid ratios use a separate right axis`() {
        val model = RatioChartAxisCalculator.calculate(
            listOf(
                RatioTrendPoint(1, "2026-01-01T00:00:00Z", 10, 1000, 0.01),
                RatioTrendPoint(2, "2026-01-02T00:00:00Z", 120, 8000, 0.015)
            )
        )!!

        assertEquals(10.0, model.rawMinimum, 0.0)
        assertEquals(8000.0, model.rawMaximum, 0.0)
        assertEquals(0.01, model.ratioMinimum!!, 0.0)
        assertEquals(0.015, model.ratioMaximum!!, 0.0)
    }

    @Test
    fun `invalid ratios are excluded from right axis without dropping raw values`() {
        val model = RatioChartAxisCalculator.calculate(
            listOf(RatioTrendPoint(1, "2026-01-01T00:00:00Z", 3, 0, null))
        )!!

        assertEquals(0.0, model.rawMinimum, 0.0)
        assertEquals(3.0, model.rawMaximum, 0.0)
        assertNull(model.ratioMinimum)
        assertNull(model.ratioMaximum)
    }
}
