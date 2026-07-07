package com.littletaro.bilibilimonitor.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import java.time.Instant

class MonitorRepository(
    private val dao: MonitorDao,
    private val api: BilibiliApi,
    private val exporter: SnapshotExporter
) {
    val videos: Flow<List<VideoEntity>> = dao.observeVideos()
    val logs: Flow<List<AppLogEntity>> = dao.observeLogs()

    fun latestSnapshot(bvId: String): Flow<VideoSnapshotEntity?> = dao.observeLatestSnapshot(bvId)

    fun snapshots(bvId: String): Flow<List<VideoSnapshotEntity>> = dao.observeSnapshots(bvId)

    suspend fun addVideo(input: String): String {
        val bvId = BvParser.parse(input)
        val now = Instant.now().toString()
        val existing = dao.videoByBvId(bvId)
        if (existing == null) {
            dao.upsertVideo(
                VideoEntity(
                    bvId = bvId,
                    aid = null,
                    title = null,
                    authorName = null,
                    authorMid = null,
                    duration = null,
                    pubdate = null,
                    sourceUrl = "https://www.bilibili.com/video/$bvId/",
                    createdAt = now,
                    updatedAt = now
                )
            )
        }
        log("INFO", "parser", "已添加视频", bvId)
        return bvId
    }

    suspend fun refresh(bvId: String) {
        withContext(Dispatchers.IO) {
            try {
                log("INFO", "network", "开始手动刷新", bvId)
                val record = api.fetchSnapshot(bvId)
                val existing = dao.videoByBvId(bvId)
                dao.upsertVideo(record.video.copy(createdAt = existing?.createdAt ?: record.video.createdAt))
                dao.insertSnapshot(record.snapshot)
                log("INFO", "network", "刷新完成", "status=${record.snapshot.fetchStatus}, bvId=$bvId")
            } catch (exc: Exception) {
                val now = Instant.now().toString()
                dao.insertSnapshot(
                    VideoSnapshotEntity(
                        bvId = bvId,
                        collectedAt = now,
                        viewCount = null,
                        danmakuCount = null,
                        replyCount = null,
                        favoriteCount = null,
                        coinCount = null,
                        shareCount = null,
                        likeCount = null,
                        sourceUrl = "https://www.bilibili.com/video/$bvId/",
                        fetchStatus = "failed",
                        errorMessage = exc.message ?: "未知错误"
                    )
                )
                log("ERROR", "network", "刷新失败", "bvId=$bvId, ${exc.message}")
            }
        }
    }

    suspend fun exportJson(bvId: String): String = withContext(Dispatchers.IO) {
        val video = dao.videoByBvId(bvId) ?: throw IllegalArgumentException("视频不存在")
        val snapshots = dao.snapshotsForExport(bvId)
        val path = exporter.exportJson(video, snapshots)
        log("INFO", "export", "JSON 导出完成", path)
        path
    }

    suspend fun exportCsv(bvId: String): String = withContext(Dispatchers.IO) {
        val video = dao.videoByBvId(bvId) ?: throw IllegalArgumentException("视频不存在")
        val snapshots = dao.snapshotsForExport(bvId)
        val path = exporter.exportCsv(video, snapshots)
        log("INFO", "export", "CSV 导出完成", path)
        path
    }

    private suspend fun log(level: String, tag: String, message: String, detail: String? = null) {
        dao.insertLog(
            AppLogEntity(
                time = Instant.now().toString(),
                level = level,
                tag = tag,
                message = message,
                detail = detail
            )
        )
    }
}
