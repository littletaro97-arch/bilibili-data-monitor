package com.littletaro.bilibilimonitor.data

data class RatioChartAxisModel(
    val rawMinimum: Double,
    val rawMaximum: Double,
    val ratioMinimum: Double?,
    val ratioMaximum: Double?
) {
    val rawSpan: Double get() = (rawMaximum - rawMinimum).takeIf { it > 0.0 } ?: 1.0
    val ratioSpan: Double? get() = ratioMinimum?.let { minimum ->
        ratioMaximum?.let { maximum -> (maximum - minimum).takeIf { it > 0.0 } ?: 1.0 }
    }
}

object RatioChartAxisCalculator {
    fun calculate(points: List<RatioTrendPoint>): RatioChartAxisModel? {
        val rawValues = points.flatMap { listOfNotNull(it.numerator?.toDouble(), it.denominator?.toDouble()) }
        if (rawValues.isEmpty()) return null
        val ratios = points.mapNotNull { it.ratio }
        return RatioChartAxisModel(
            rawMinimum = rawValues.min(),
            rawMaximum = rawValues.max(),
            ratioMinimum = ratios.minOrNull(),
            ratioMaximum = ratios.maxOrNull()
        )
    }
}
