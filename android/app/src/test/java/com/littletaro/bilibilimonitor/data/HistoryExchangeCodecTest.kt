package com.littletaro.bilibilimonitor.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HistoryExchangeCodecTest {
    private val video = VideoEntity("BV1xx411c7mD", 1, "中文😀", "UP", 2, 60, 1_700_000_000, "https://i0.hdslb.com/bfs/archive/cover.jpg", "https://www.bilibili.com/video/BV1xx411c7mD", "2026-01-01T08:00:00+08:00", "2026-01-01T08:00:00+08:00")
    private val snapshot = VideoSnapshotEntity(bvId = video.bvId, collectedAt = "2026-01-01T08:00:00+08:00", viewCount = 100, danmakuCount = 2, replyCount = 3, favoriteCount = 4, coinCount = 5, shareCount = 6, likeCount = 7, sourceUrl = video.sourceUrl, fetchStatus = "success", errorMessage = null, captureSource = SnapshotSources.MANUAL)

    @Test fun roundTripUsesUtcAndSource() {
        val bytes = HistoryExchangeCodec.export(listOf(video), listOf(snapshot), "test")
        val preview = HistoryExchangeCodec.preview(bytes)
        assertEquals(1, preview.videoCount)
        assertEquals(1, preview.snapshotCount)
        assertEquals("2026-01-01T00:00:00Z", preview.packageData.snapshots.single().collectedAt)
        assertEquals(SnapshotSources.MANUAL, preview.packageData.snapshots.single().captureSource)
        assertEquals("https://i0.hdslb.com/bfs/archive/cover.jpg", preview.packageData.videos.single().coverUrl)
    }

    @Test fun invalidZipIsRejected() {
        val error = runCatching { HistoryExchangeCodec.preview("not zip".toByteArray()) }.exceptionOrNull()
        assertTrue(error is IllegalArgumentException)
    }

    @Test fun digestChangesWhenContentChanges() {
        assertTrue(HistoryExchangeCodec.snapshotDigest(snapshot) != HistoryExchangeCodec.snapshotDigest(snapshot.copy(viewCount = 101)))
    }
}
