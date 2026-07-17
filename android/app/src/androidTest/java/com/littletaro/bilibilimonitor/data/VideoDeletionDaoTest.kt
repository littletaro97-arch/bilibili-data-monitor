package com.littletaro.bilibilimonitor.data

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class VideoDeletionDaoTest {
    private val database = Room.inMemoryDatabaseBuilder(
        ApplicationProvider.getApplicationContext<Context>(),
        AppDatabase::class.java
    ).allowMainThreadQueries().build()

    @After fun close() = database.close()

    @Test fun recycleBinKeepsSnapshotsUntilExplicitPermanentDeletion() = runBlocking {
        val dao = database.dao()
        val video = VideoEntity(
            bvId = "BV1xx411c7mD", aid = null, title = "test", authorName = null,
            authorMid = null, duration = null, pubdate = null, coverUrl = null,
            sourceUrl = null, createdAt = "2026-01-01T00:00:00Z", updatedAt = "2026-01-01T00:00:00Z"
        )
        dao.upsertVideo(video)
        dao.insertSnapshot(
            VideoSnapshotEntity(
                bvId = video.bvId, collectedAt = "2026-01-01T00:00:00Z", viewCount = 1,
                danmakuCount = null, replyCount = null, favoriteCount = null, coinCount = null,
                shareCount = null, likeCount = null, sourceUrl = null, fetchStatus = "success", errorMessage = null
            )
        )

        assertEquals(1, dao.moveToRecycleBin(video.bvId, "2026-01-02T00:00:00Z"))
        assertTrue(dao.observeVideos().first().isEmpty())
        assertEquals(1, dao.observeDeletedVideos().first().size)
        assertEquals(1, dao.snapshotsForExport(video.bvId).size)

        assertEquals(1, dao.restoreVideo(video.bvId, "2026-01-03T00:00:00Z"))
        assertEquals(1, dao.observeVideos().first().size)

        assertTrue(dao.permanentlyDeleteVideo(video.bvId))
        assertNull(dao.videoByBvId(video.bvId))
        assertTrue(dao.snapshotsForExport(video.bvId).isEmpty())
    }
}
