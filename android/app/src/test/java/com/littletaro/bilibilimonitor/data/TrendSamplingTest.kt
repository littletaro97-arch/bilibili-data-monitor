package com.littletaro.bilibilimonitor.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class TrendSamplingTest {
    @Test fun allRangeBoundsCanvasWorkAndPreservesEndpointsAndPeak() {
        val snapshots = (0 until 5_000).map { index ->
            snapshot(index.toLong(), index.toLong(), if (index == 2_173) 9_999_999 else index.toLong())
        }
        val selection = TrendCalculator.select(
            snapshots, TrendRange.ALL, 320,
            listOf { snapshot -> TrendCalculator.valueOf(snapshot, TrendMetric.VIEW)?.toDouble() }
        )

        assertEquals(5_000, selection.originalRecordCount)
        assertTrue(selection.displayedSnapshots.size <= 320)
        assertTrue(selection.isOptimized)
        assertEquals(0L, selection.displayedSnapshots.first().id)
        assertEquals(4_999L, selection.displayedSnapshots.last().id)
        assertTrue(selection.displayedSnapshots.any { it.viewCount == 9_999_999L })
    }

    @Test fun ratioSamplingKeepsWholeSnapshotsAndBothMetricExtremes() {
        val snapshots = (0 until 500).map { index ->
            snapshot(
                id = index.toLong(),
                seconds = index.toLong(),
                view = if (index == 211) 5_000_000 else 1_000 + index.toLong(),
                like = if (index == 343) 999_999 else index.toLong() + 1
            )
        }
        val selection = TrendCalculator.select(
            snapshots, TrendRange.ALL, 160,
            listOf(
                { snapshot: VideoSnapshotEntity -> TrendCalculator.valueOf(snapshot, TrendMetric.LIKE)?.toDouble() },
                { snapshot: VideoSnapshotEntity -> TrendCalculator.valueOf(snapshot, TrendMetric.VIEW)?.toDouble() },
                { snapshot: VideoSnapshotEntity ->
                    val likes = snapshot.likeCount
                    val views = snapshot.viewCount
                    if (likes != null && views != null && views != 0L) likes.toDouble() / views else null
                }
            )
        )
        val ratio = TrendCalculator.ratioPoints(selection.displayedSnapshots, TrendMetric.LIKE, TrendMetric.VIEW)

        assertTrue(selection.displayedSnapshots.any { it.id == 211L })
        assertTrue(selection.displayedSnapshots.any { it.id == 343L })
        assertEquals(selection.displayedSnapshots.map { it.id }, ratio.map { it.snapshotId })
    }

    @Test fun ratioTreatsZeroAndMissingDenominatorAsInvalidInsteadOfZero() {
        val zero = snapshot(1, 1, 0, 5)
        val missing = snapshot(2, 2, null, 5)
        val valid = snapshot(3, 3, 100, 5)
        val result = TrendCalculator.ratioPoints(listOf(zero, missing, valid), TrendMetric.LIKE, TrendMetric.VIEW)

        assertNull(result[0].ratio)
        assertNull(result[1].ratio)
        assertEquals(0.05, result[2].ratio!!, 0.000001)
    }

    @Test fun largeRatioSelectionUsesOneSharedSampleForBothAxesAndRatio() {
        val snapshots = (0 until 5_000).map { index ->
            snapshot(
                id = index.toLong(),
                seconds = index.toLong(),
                view = if (index == 4_321) 8_000_000 else 1_000 + index.toLong(),
                like = if (index == 1_234) 700_000 else 10 + index.toLong()
            )
        }
        val selected = TrendCalculator.select(
            snapshots, TrendRange.ALL, TrendCalculator.targetPointCount(800, 3),
            listOf(
                { it.likeCount?.toDouble() },
                { it.viewCount?.toDouble() },
                { snapshot ->
                    val likes = snapshot.likeCount
                    val views = snapshot.viewCount
                    if (likes != null && views != null && views != 0L) likes.toDouble() / views else null
                }
            )
        )
        val points = TrendCalculator.ratioPoints(selected.displayedSnapshots, TrendMetric.LIKE, TrendMetric.VIEW)

        assertTrue(selected.displayedSnapshots.size <= TrendCalculator.targetPointCount(800, 3))
        assertTrue(selected.displayedSnapshots.any { it.id == 1_234L })
        assertTrue(selected.displayedSnapshots.any { it.id == 4_321L })
        assertEquals(selected.displayedSnapshots.map { it.id }, points.map { it.snapshotId })
    }

    @Test fun recentRangesDoNotSampleOrLoadMoreThanTheirRange() {
        val snapshots = (0 until 100).map { snapshot(it.toLong(), it.toLong(), it.toLong()) }
        val twenty = TrendCalculator.select(snapshots, TrendRange.TWENTY, 120, listOf { it.viewCount?.toDouble() })
        val fifty = TrendCalculator.select(snapshots, TrendRange.FIFTY, 120, listOf { it.viewCount?.toDouble() })

        assertEquals(20, twenty.displayedSnapshots.size)
        assertEquals(50, fifty.displayedSnapshots.size)
        assertFalse(twenty.isOptimized)
        assertEquals(120, TrendCalculator.targetPointCount(100, 1))
        assertTrue(TrendCalculator.targetPointCount(2_000, 3) > TrendCalculator.targetPointCount(500, 3))
    }

    @Test fun recordsPressureSamplingTimingsForOneHundredToFiveThousandRows() {
        listOf(100, 500, 5_000).forEach { count ->
            val snapshots = (0 until count).map { index -> snapshot(index.toLong(), index.toLong(), index.toLong()) }
            val started = System.nanoTime()
            val selection = TrendCalculator.select(
                snapshots, TrendRange.ALL, 360,
                listOf { it.viewCount?.toDouble() }
            )
            val elapsedMillis = (System.nanoTime() - started) / 1_000_000.0
            println("TREND_PERF count=$count raw=${selection.originalRecordCount} displayed=${selection.displayedSnapshots.size} sampleMs=$elapsedMillis")
            assertTrue(selection.displayedSnapshots.size <= 360)
        }
    }

    private fun snapshot(id: Long, seconds: Long, view: Long?, like: Long? = 1): VideoSnapshotEntity =
        VideoSnapshotEntity(
            id = id,
            bvId = "BV1xx411c7mD",
            collectedAt = Instant.ofEpochSecond(seconds).toString(),
            viewCount = view,
            danmakuCount = null,
            replyCount = null,
            favoriteCount = null,
            coinCount = null,
            shareCount = null,
            likeCount = like,
            sourceUrl = null,
            fetchStatus = "success",
            errorMessage = null,
            collectedAtEpochMillis = seconds * 1_000
        )
}
