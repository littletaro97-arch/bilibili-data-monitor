package com.littletaro.bilibilimonitor.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface MonitorDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertVideo(video: VideoEntity)

    @Insert
    suspend fun insertSnapshot(snapshot: VideoSnapshotEntity): Long

    @Insert
    suspend fun insertLog(log: AppLogEntity)

    @Query("SELECT * FROM videos ORDER BY updatedAt DESC")
    fun observeVideos(): Flow<List<VideoEntity>>

    @Query("SELECT * FROM video_snapshots WHERE bvId = :bvId ORDER BY collectedAt DESC, id DESC LIMIT 1")
    fun observeLatestSnapshot(bvId: String): Flow<VideoSnapshotEntity?>

    @Query("SELECT * FROM video_snapshots WHERE bvId = :bvId ORDER BY collectedAt DESC, id DESC")
    fun observeSnapshots(bvId: String): Flow<List<VideoSnapshotEntity>>

    @Query("SELECT * FROM video_snapshots WHERE bvId = :bvId ORDER BY collectedAt DESC, id DESC")
    suspend fun snapshotsForExport(bvId: String): List<VideoSnapshotEntity>

    @Query("SELECT * FROM videos WHERE bvId = :bvId")
    suspend fun videoByBvId(bvId: String): VideoEntity?

    @Query("SELECT * FROM app_logs ORDER BY time DESC, id DESC LIMIT 200")
    fun observeLogs(): Flow<List<AppLogEntity>>
}
