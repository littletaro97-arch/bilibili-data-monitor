package com.littletaro.bilibilimonitor.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

@Dao
interface MonitorDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertVideo(video: VideoEntity)

    @Insert
    suspend fun insertSnapshot(snapshot: VideoSnapshotEntity): Long

    @Insert
    suspend fun insertLog(log: AppLogEntity)

    @Query("SELECT * FROM videos WHERE deletedAt IS NULL ORDER BY updatedAt DESC")
    fun observeVideos(): Flow<List<VideoEntity>>

    @Query("SELECT * FROM videos WHERE deletedAt IS NULL ORDER BY updatedAt DESC")
    suspend fun videosForRefresh(): List<VideoEntity>

    @Query("SELECT * FROM videos WHERE deletedAt IS NULL ORDER BY bvId ASC")
    suspend fun allVideosForExchange(): List<VideoEntity>

    @Query("SELECT * FROM video_snapshots WHERE bvId IN (SELECT bvId FROM videos WHERE deletedAt IS NULL) ORDER BY bvId ASC, collectedAt ASC, id ASC")
    suspend fun allSnapshotsForExchange(): List<VideoSnapshotEntity>

    @Query("SELECT * FROM videos WHERE deletedAt IS NOT NULL ORDER BY deletedAt DESC, bvId ASC")
    fun observeDeletedVideos(): Flow<List<VideoEntity>>

    @Query("UPDATE videos SET deletedAt = :deletedAt WHERE bvId = :bvId AND deletedAt IS NULL")
    suspend fun moveToRecycleBin(bvId: String, deletedAt: String): Int

    @Query("UPDATE videos SET deletedAt = NULL, updatedAt = :restoredAt WHERE bvId = :bvId AND deletedAt IS NOT NULL")
    suspend fun restoreVideo(bvId: String, restoredAt: String): Int

    @Query("DELETE FROM video_snapshots WHERE bvId = :bvId")
    suspend fun deleteSnapshotsForVideo(bvId: String): Int

    @Query("DELETE FROM videos WHERE bvId = :bvId")
    suspend fun deleteVideo(bvId: String): Int

    @Transaction
    suspend fun permanentlyDeleteVideo(bvId: String): Boolean {
        deleteSnapshotsForVideo(bvId)
        return deleteVideo(bvId) > 0
    }

    @Query("SELECT * FROM video_snapshots WHERE bvId=:bvId AND captureSource=:captureSource ORDER BY id ASC")
    suspend fun snapshotsByExchangeSource(bvId: String, captureSource: String): List<VideoSnapshotEntity>

    @Transaction
    suspend fun mergeHistoryExchange(packageData: HistoryExchangePackage): HistoryImportReport {
        var videosAdded = 0
        var snapshotsAdded = 0
        var duplicates = 0
        var conflicts = 0
        packageData.videos.forEach { incoming ->
            val existing = videoByBvId(incoming.bvId)
            if (existing == null) {
                upsertVideo(incoming)
                videosAdded++
            }
        }
        packageData.snapshots.forEach { incoming ->
            val incomingInstant = DeviceTime.parseToInstant(incoming.collectedAt)
            val identityMatches = snapshotsByExchangeSource(incoming.bvId, incoming.captureSource)
                .filter { DeviceTime.parseToInstant(it.collectedAt) == incomingInstant }
            val incomingDigest = incoming.exchangeDigest ?: HistoryExchangeCodec.snapshotDigest(incoming)
            if (identityMatches.isEmpty()) {
                if (videoByBvId(incoming.bvId) == null) {
                    conflicts++
                } else {
                    insertSnapshot(incoming.copy(exchangeDigest = incomingDigest))
                    snapshotsAdded++
                }
            } else if (identityMatches.any { (it.exchangeDigest ?: HistoryExchangeCodec.snapshotDigest(it)) == incomingDigest }) {
                duplicates++
            } else {
                conflicts++
            }
        }
        return HistoryImportReport(videosAdded, snapshotsAdded, duplicates, conflicts)
    }

    @Query("SELECT * FROM video_snapshots WHERE bvId = :bvId ORDER BY collectedAtEpochMillis DESC, id DESC LIMIT 1")
    fun observeLatestSnapshot(bvId: String): Flow<VideoSnapshotEntity?>

    @Query("SELECT * FROM video_snapshots WHERE bvId = :bvId AND fetchStatus != 'failed' ORDER BY collectedAtEpochMillis DESC, id DESC LIMIT 2")
    fun observeLatestValidSnapshots(bvId: String): Flow<List<VideoSnapshotEntity>>

    @Query("SELECT * FROM video_snapshots WHERE bvId = :bvId ORDER BY collectedAtEpochMillis DESC, id DESC")
    fun observeSnapshots(bvId: String): Flow<List<VideoSnapshotEntity>>

    @Query("SELECT * FROM video_snapshots WHERE bvId = :bvId ORDER BY collectedAtEpochMillis DESC, id DESC")
    suspend fun snapshotsForExport(bvId: String): List<VideoSnapshotEntity>

    @Query("SELECT * FROM videos WHERE bvId = :bvId")
    suspend fun videoByBvId(bvId: String): VideoEntity?

    @Query("SELECT * FROM app_logs ORDER BY time DESC, id DESC LIMIT 200")
    fun observeLogs(): Flow<List<AppLogEntity>>
}
