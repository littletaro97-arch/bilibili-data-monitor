package com.littletaro.bilibilimonitor.data

import kotlin.math.max

enum class TrendMetric(val label: String) {
    VIEW("播放"),
    LIKE("点赞"),
    REPLY("评论"),
    COIN("投币"),
    FAVORITE("收藏"),
    DANMAKU("弹幕"),
    SHARE("分享")
}

enum class TrendRange(val label: String, val recordLimit: Int?) {
    TWENTY("20", 20),
    FIFTY("50", 50),
    ALL("全部", null)
}

data class TrendPoint(
    val snapshotId: Long,
    val collectedAt: String,
    val value: Long?,
    val delta: Long?,
    val captureSource: String = SnapshotSources.UNKNOWN
)

data class RatioTrendPoint(
    val snapshotId: Long,
    val collectedAt: String,
    val numerator: Long?,
    val denominator: Long?,
    val ratio: Double?,
    val captureSource: String = SnapshotSources.UNKNOWN
)

data class TrendSelection(
    val originalRecordCount: Int,
    val displayedSnapshots: List<VideoSnapshotEntity>
) {
    val isOptimized: Boolean get() = originalRecordCount > displayedSnapshots.size
}

object TrendCalculator {
    /**
     * The point budget is based on actual graph width and the number of lines. It caps Canvas work,
     * while still permitting wide screens to retain substantially more detail than narrow screens.
     */
    fun targetPointCount(availableWidthPx: Int, seriesCount: Int): Int {
        val pixelsPerPoint = if (seriesCount <= 1) 4 else 7
        return (availableWidthPx.coerceAtLeast(1) / pixelsPerPoint).coerceIn(120, 720)
    }

    fun select(
        snapshots: List<VideoSnapshotEntity>,
        range: TrendRange,
        targetPointCount: Int,
        valueSeries: List<(VideoSnapshotEntity) -> Double?>
    ): TrendSelection {
        val chronological = snapshots.sortedWith(snapshotOldestFirst)
        val scoped = range.recordLimit?.let { chronological.takeLast(it) } ?: chronological
        if (scoped.size <= targetPointCount || scoped.size < 3) {
            return TrendSelection(scoped.size, scoped)
        }

        val perBucketMaximum = 2 + valueSeries.size * 2
        val bucketCount = max(1, targetPointCount / perBucketMaximum)
        val firstEpoch = epochOf(scoped.first())
        val lastEpoch = epochOf(scoped.last())
        val duration = (lastEpoch - firstEpoch).takeIf { it > 0L }
        val buckets = Array(bucketCount) { mutableListOf<IndexedValue<VideoSnapshotEntity>>() }
        scoped.forEachIndexed { index, snapshot ->
            val bucket = if (duration == null) {
                (index.toLong() * bucketCount / scoped.size).toInt()
            } else {
                (((epochOf(snapshot) - firstEpoch) * bucketCount) / (duration + 1)).toInt()
            }.coerceIn(0, bucketCount - 1)
            buckets[bucket] += IndexedValue(index, snapshot)
        }

        val selectedIndexes = linkedSetOf<Int>()
        buckets.forEach { bucket ->
            if (bucket.isEmpty()) return@forEach
            selectedIndexes += bucket.first().index
            selectedIndexes += bucket.last().index
            valueSeries.forEach { series ->
                bucket.mapNotNull { item -> series(item.value)?.let { item to it } }
                    .let { values ->
                        values.minByOrNull { it.second }?.first?.let { selectedIndexes += it.index }
                        values.maxByOrNull { it.second }?.first?.let { selectedIndexes += it.index }
                    }
            }
        }
        selectedIndexes += 0
        selectedIndexes += scoped.lastIndex
        val displayed = selectedIndexes.sorted().map(scoped::get)
        return TrendSelection(scoped.size, displayed)
    }

    fun points(
        snapshots: List<VideoSnapshotEntity>,
        metric: TrendMetric,
        limit: Int
    ): List<TrendPoint> {
        val range = when (limit) {
            50 -> TrendRange.FIFTY
            20 -> TrendRange.TWENTY
            else -> TrendRange.TWENTY
        }
        val selection = select(snapshots, range, Int.MAX_VALUE, listOf { valueOf(it, metric)?.toDouble() })
        return points(selection.displayedSnapshots, metric)
    }

    fun points(snapshots: List<VideoSnapshotEntity>, metric: TrendMetric): List<TrendPoint> {
        var previous: Long? = null
        return snapshots.map { snapshot ->
            val value = valueOf(snapshot, metric)
            val delta = if (value != null && previous != null) value - previous!! else null
            if (value != null) previous = value
            TrendPoint(snapshot.id, snapshot.collectedAt, value, delta, snapshot.captureSource)
        }
    }

    fun ratioPoints(
        snapshots: List<VideoSnapshotEntity>,
        numeratorMetric: TrendMetric,
        denominatorMetric: TrendMetric
    ): List<RatioTrendPoint> = snapshots.map { snapshot ->
        val numerator = valueOf(snapshot, numeratorMetric)
        val denominator = valueOf(snapshot, denominatorMetric)
        RatioTrendPoint(
            snapshotId = snapshot.id,
            collectedAt = snapshot.collectedAt,
            numerator = numerator,
            denominator = denominator,
            ratio = if (numerator != null && denominator != null && denominator != 0L) {
                numerator.toDouble() / denominator.toDouble()
            } else null,
            captureSource = snapshot.captureSource
        )
    }

    fun valueOf(snapshot: VideoSnapshotEntity, metric: TrendMetric): Long? =
        when (metric) {
            TrendMetric.VIEW -> snapshot.viewCount
            TrendMetric.LIKE -> snapshot.likeCount
            TrendMetric.REPLY -> snapshot.replyCount
            TrendMetric.COIN -> snapshot.coinCount
            TrendMetric.FAVORITE -> snapshot.favoriteCount
            TrendMetric.DANMAKU -> snapshot.danmakuCount
            TrendMetric.SHARE -> snapshot.shareCount
        }

    private fun epochOf(snapshot: VideoSnapshotEntity): Long =
        snapshot.collectedAtEpochMillis.takeIf { it > 0L } ?: SnapshotTime.epochMillis(snapshot.collectedAt)

    private val snapshotOldestFirst = Comparator<VideoSnapshotEntity> { left, right ->
        DeviceTime.compareAbsolute(left.collectedAt, right.collectedAt).takeIf { it != 0 }
            ?: left.id.compareTo(right.id)
    }
}
