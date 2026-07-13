package com.littletaro.bilibilimonitor.data

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(tableName = "videos")
data class VideoEntity(
    @PrimaryKey val bvId: String,
    val aid: Long?,
    val title: String?,
    val authorName: String?,
    val authorMid: Long?,
    val duration: Long?,
    val pubdate: Long?,
    val coverUrl: String?,
    val sourceUrl: String?,
    val createdAt: String,
    val updatedAt: String
)

@Entity(
    tableName = "video_snapshots",
    indices = [
        Index(value = ["bvId", "collectedAt"]),
        Index(value = ["bvId", "collectedAtEpochMillis", "id"])
    ]
)
data class VideoSnapshotEntity @JvmOverloads constructor(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val bvId: String,
    val collectedAt: String,
    val viewCount: Long?,
    val danmakuCount: Long?,
    val replyCount: Long?,
    val favoriteCount: Long?,
    val coinCount: Long?,
    val shareCount: Long?,
    val likeCount: Long?,
    val sourceUrl: String?,
    val fetchStatus: String,
    val errorMessage: String?,
    val captureSource: String = SnapshotSources.UNKNOWN,
    val exchangeDigest: String? = null,
    val collectedAtEpochMillis: Long = SnapshotTime.epochMillis(collectedAt)
)

object SnapshotTime {
    fun epochMillis(collectedAt: String): Long =
        DeviceTime.parseToInstant(collectedAt)?.toEpochMilli() ?: 0L
}

object SnapshotSources {
    const val MANUAL = "MANUAL"
    const val AUTO = "AUTO"
    const val UNKNOWN = "UNKNOWN"

    fun from(trigger: RefreshTrigger): String =
        if (trigger == RefreshTrigger.AUTO) AUTO else MANUAL

    fun sanitize(value: String): String = when (value) {
        MANUAL, AUTO, UNKNOWN -> value
        else -> UNKNOWN
    }
}

@Entity(tableName = "app_logs")
data class AppLogEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val time: String,
    val level: String,
    val tag: String,
    val message: String,
    val detail: String?
)

data class VideoSnapshotRecord(
    val video: VideoEntity,
    val snapshot: VideoSnapshotEntity
)
