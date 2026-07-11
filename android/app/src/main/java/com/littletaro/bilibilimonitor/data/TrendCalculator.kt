package com.littletaro.bilibilimonitor.data

enum class TrendMetric(val label: String) {
    VIEW("播放"),
    LIKE("点赞"),
    REPLY("评论"),
    COIN("投币"),
    FAVORITE("收藏")
}

data class TrendPoint(
    val collectedAt: String,
    val value: Long?,
    val delta: Long?,
    val captureSource: String = SnapshotSources.UNKNOWN
)

object TrendCalculator {
    fun points(
        snapshots: List<VideoSnapshotEntity>,
        metric: TrendMetric,
        limit: Int
    ): List<TrendPoint> {
        val safeLimit = when (limit) {
            20, 50 -> limit
            else -> 20
        }
        val chronological = snapshots
            .sortedWith { left, right ->
                DeviceTime.compareAbsolute(left.collectedAt, right.collectedAt).takeIf { it != 0 }
                    ?: left.id.compareTo(right.id)
            }
            .takeLast(safeLimit)

        var previous: Long? = null
        return chronological.map { snapshot ->
            val value = valueOf(snapshot, metric)
            val delta = if (value != null && previous != null) value - previous!! else null
            if (value != null) previous = value
            TrendPoint(snapshot.collectedAt, value, delta, snapshot.captureSource)
        }
    }

    fun valueOf(snapshot: VideoSnapshotEntity, metric: TrendMetric): Long? =
        when (metric) {
            TrendMetric.VIEW -> snapshot.viewCount
            TrendMetric.LIKE -> snapshot.likeCount
            TrendMetric.REPLY -> snapshot.replyCount
            TrendMetric.COIN -> snapshot.coinCount
            TrendMetric.FAVORITE -> snapshot.favoriteCount
        }
}
