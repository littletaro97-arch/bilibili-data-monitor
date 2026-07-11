package com.littletaro.bilibilimonitor.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext

enum class RefreshTrigger(val logLabel: String) {
    MANUAL("manual"),
    AUTO("auto")
}

data class RefreshAllResult(
    val total: Int,
    val success: Int,
    val failed: Int
)

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
            try {
                withContext(Dispatchers.IO) {
                    BilibiliApi.resolveSharedBvId(input, api.client)
                }
            } catch (resolveExc: Exception) {
                writeLog("warning", "parser", "BV 解析失败", resolveExc.message ?: exc.message)
                throw IllegalArgumentException(resolveExc.message ?: exc.message ?: "未找到有效的哔哩哔哩视频链接")
            }
        }
        return try {
            val now = DeviceTime.nowIsoString()
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
                writeLog("info", "database", "视频写入成功", bvId)
            } else {
                writeLog("info", "database", "视频已存在，未重复创建", bvId)
            }
            writeLog("info", "parser", "BV 解析成功", bvId)
            bvId
        } catch (exc: Exception) {
            writeLog("error", "database", "视频写入失败", "bvId=$bvId, ${exc.message}")
            throw exc
        }
    }

    suspend fun refresh(bvId: String, trigger: RefreshTrigger = RefreshTrigger.MANUAL) {
        withContext(Dispatchers.IO) {
            try {
                writeLog("info", "network", "${trigger.logLabel} 刷新请求开始", bvId)
                val record = api.fetchSnapshot(bvId)
                val existing = dao.videoByBvId(bvId)
                dao.upsertVideo(record.video.copy(createdAt = existing?.createdAt ?: record.video.createdAt))
                dao.insertSnapshot(record.snapshot.copy(captureSource = SnapshotSources.from(trigger)))
                writeLog("info", "database", "${trigger.logLabel} 快照写入成功", "status=${record.snapshot.fetchStatus}, bvId=$bvId")
                writeLog("info", "network", "${trigger.logLabel} 刷新请求成功", "status=${record.snapshot.fetchStatus}, bvId=$bvId")
            } catch (exc: Exception) {
                val now = DeviceTime.nowIsoString()
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
                            errorMessage = message,
                            captureSource = SnapshotSources.from(trigger)
                        )
                    )
                    writeLog("warning", "database", "${trigger.logLabel} 失败快照已写入", bvId)
                } catch (dbExc: Exception) {
                    writeLog("error", "database", "数据库写入失败", "bvId=$bvId, ${dbExc.message}")
                }
                writeLog("error", "network", "${trigger.logLabel} 刷新请求失败", "bvId=$bvId, ${exc.javaClass.simpleName}: $message")
                throw exc
            }
        }
    }

    suspend fun refreshAllExistingVideos(trigger: RefreshTrigger): RefreshAllResult = withContext(Dispatchers.IO) {
        val videos = dao.videosForRefresh()
        writeLog("info", "work", "${trigger.logLabel} 批量刷新开始", "videos=${videos.size}")
        var success = 0
        var failed = 0
        videos.forEach { video ->
            try {
                refresh(video.bvId, trigger)
                success += 1
            } catch (_: Exception) {
                failed += 1
            }
        }
        writeLog("info", "work", "${trigger.logLabel} 批量刷新完成", "total=${videos.size}, success=$success, failed=$failed")
        RefreshAllResult(total = videos.size, success = success, failed = failed)
    }

    suspend fun exportJson(bvId: String): ExportResult = withContext(Dispatchers.IO) {
        try {
            val video = dao.videoByBvId(bvId) ?: throw IllegalArgumentException("视频不存在")
            val snapshots = dao.snapshotsForExport(bvId)
            val result = exporter.exportJson(video, snapshots)
            writeLog("info", "export", "JSON 导出成功", "${result.fileName}, ${result.sizeBytes} bytes, ${result.path}")
            result
        } catch (exc: Exception) {
            writeLog("error", "export", "JSON 导出失败", "bvId=$bvId, ${exc.message}")
            throw exc
        }
    }

    suspend fun exportCsv(bvId: String): ExportResult = withContext(Dispatchers.IO) {
        try {
            val video = dao.videoByBvId(bvId) ?: throw IllegalArgumentException("视频不存在")
            val snapshots = dao.snapshotsForExport(bvId)
            val result = exporter.exportCsv(video, snapshots)
            writeLog("info", "export", "CSV 导出成功", "${result.fileName}, ${result.sizeBytes} bytes, ${result.path}")
            result
        } catch (exc: Exception) {
            writeLog("error", "export", "CSV 导出失败", "bvId=$bvId, ${exc.message}")
            throw exc
        }
    }

    suspend fun jsonPayload(bvId: String): ExportPayload = withContext(Dispatchers.IO) {
        val video = dao.videoByBvId(bvId) ?: throw IllegalArgumentException("视频不存在")
        exporter.jsonPayload(video, dao.snapshotsForExport(bvId))
    }

    suspend fun csvPayload(bvId: String): ExportPayload = withContext(Dispatchers.IO) {
        val video = dao.videoByBvId(bvId) ?: throw IllegalArgumentException("视频不存在")
        exporter.csvPayload(video, dao.snapshotsForExport(bvId))
    }

    suspend fun writeLog(level: String, tag: String, message: String, detail: String? = null) {
        dao.insertLog(
            AppLogEntity(
                time = DeviceTime.nowIsoString(),
                level = level,
                tag = tag,
                message = message,
                detail = detail
            )
        )
    }
}
