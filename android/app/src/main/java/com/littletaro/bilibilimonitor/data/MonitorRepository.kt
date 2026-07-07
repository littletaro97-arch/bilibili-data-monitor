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
        val bvId = try {
            BvParser.parse(input)
        } catch (exc: IllegalArgumentException) {
            log("warning", "parser", "BV 解析失败", exc.message)
            throw exc
        }
        return try {
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
                log("info", "database", "视频写入成功", bvId)
            } else {
                log("info", "database", "视频已存在，未重复创建", bvId)
            }
            log("info", "parser", "BV 解析成功", bvId)
            bvId
        } catch (exc: Exception) {
            log("error", "database", "视频写入失败", "bvId=$bvId, ${exc.message}")
            throw exc
        }
    }

    suspend fun refresh(bvId: String) {
        withContext(Dispatchers.IO) {
            try {
                log("info", "network", "网络请求开始", bvId)
                val record = api.fetchSnapshot(bvId)
                val existing = dao.videoByBvId(bvId)
                dao.upsertVideo(record.video.copy(createdAt = existing?.createdAt ?: record.video.createdAt))
                dao.insertSnapshot(record.snapshot)
                log("info", "database", "快照写入成功", "status=${record.snapshot.fetchStatus}, bvId=$bvId")
                log("info", "network", "网络请求成功", "status=${record.snapshot.fetchStatus}, bvId=$bvId")
            } catch (exc: Exception) {
                val now = Instant.now().toString()
                val message = exc.message ?: "未知错误"
                try {
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
                            errorMessage = message
                        )
                    )
                    log("warning", "database", "失败快照已写入", bvId)
                } catch (dbExc: Exception) {
                    log("error", "database", "数据库写入失败", "bvId=$bvId, ${dbExc.message}")
                }
                log("error", "network", "网络请求失败", "bvId=$bvId, ${exc.javaClass.simpleName}: $message")
            }
        }
    }

    suspend fun exportJson(bvId: String): ExportResult = withContext(Dispatchers.IO) {
        try {
            val video = dao.videoByBvId(bvId) ?: throw IllegalArgumentException("视频不存在")
            val snapshots = dao.snapshotsForExport(bvId)
            val result = exporter.exportJson(video, snapshots)
            log("info", "export", "JSON 导出成功", "${result.fileName}, ${result.path}")
            result
        } catch (exc: Exception) {
            log("error", "export", "JSON 导出失败", "bvId=$bvId, ${exc.message}")
            throw exc
        }
    }

    suspend fun exportCsv(bvId: String): ExportResult = withContext(Dispatchers.IO) {
        try {
            val video = dao.videoByBvId(bvId) ?: throw IllegalArgumentException("视频不存在")
            val snapshots = dao.snapshotsForExport(bvId)
            val result = exporter.exportCsv(video, snapshots)
            log("info", "export", "CSV 导出成功", "${result.fileName}, ${result.path}")
            result
        } catch (exc: Exception) {
            log("error", "export", "CSV 导出失败", "bvId=$bvId, ${exc.message}")
            throw exc
        }
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
