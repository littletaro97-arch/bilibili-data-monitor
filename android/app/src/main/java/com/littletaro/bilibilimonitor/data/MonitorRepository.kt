package com.littletaro.bilibilimonitor.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext
import java.util.UUID

enum class RefreshTrigger(val logLabel: String) {
    MANUAL("manual"),
    AUTO("auto")
}

data class RefreshAllResult(
    val total: Int,
    val success: Int,
    val failed: Int
)

data class LatestSnapshotComparison(
    val current: VideoSnapshotEntity,
    val previous: VideoSnapshotEntity?
)

class MonitorRepository(
    private val dao: MonitorDao,
    private val api: BilibiliApi,
    private val exporter: SnapshotExporter,
    private val deviceId: String
) {
    val videos: Flow<List<VideoEntity>> = dao.observeVideos()
    val recycleBinVideos: Flow<List<VideoEntity>> = dao.observeDeletedVideos()
    val logs: Flow<List<AppLogEntity>> = dao.observeLogs()

    fun latestSnapshot(bvId: String): Flow<VideoSnapshotEntity?> =
        dao.observeLatestSnapshot(bvId)

    fun latestValidSnapshotComparison(bvId: String): Flow<LatestSnapshotComparison?> =
        dao.observeLatestValidSnapshots(bvId).map { rows ->
            rows.firstOrNull()?.let { LatestSnapshotComparison(it, rows.getOrNull(1)) }
        }

    fun snapshots(bvId: String): Flow<List<VideoSnapshotEntity>> = dao.observeSnapshots(bvId)
        .map { rows -> rows.sortedWith(snapshotNewestFirst) }
        .flowOn(Dispatchers.Default)

    suspend fun initializeSyncIdentity() = withContext(Dispatchers.IO) {
        dao.backfillSnapshotOrigins(deviceId)
    }

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
                        coverUrl = null,
                        sourceUrl = "https://www.bilibili.com/video/$bvId/",
                        createdAt = now,
                        updatedAt = now
                    )
                )
                writeLog("info", "database", "视频写入成功", bvId)
            } else if (existing.deletedAt != null) {
                dao.restoreVideo(bvId, now)
                writeLog("info", "database", "视频已从回收站恢复", bvId)
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
                dao.upsertVideo(
                    record.video.copy(
                        createdAt = existing?.createdAt ?: record.video.createdAt,
                        coverUrl = record.video.coverUrl ?: existing?.coverUrl
                    )
                )
                dao.insertSnapshot(record.snapshot.copy(
                    captureSource = SnapshotSources.from(trigger),
                    originDeviceId = deviceId,
                    originSnapshotId = UUID.randomUUID().toString()
                ))
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
                            captureSource = SnapshotSources.from(trigger),
                            originDeviceId = deviceId,
                            originSnapshotId = UUID.randomUUID().toString()
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

    suspend fun moveToRecycleBin(bvId: String): Boolean = withContext(Dispatchers.IO) {
        val moved = dao.moveToRecycleBin(bvId, DeviceTime.nowIsoString()) > 0
        if (moved) writeLog("info", "database", "视频已移至回收站", bvId)
        moved
    }

    suspend fun restoreFromRecycleBin(bvId: String): Boolean = withContext(Dispatchers.IO) {
        val restored = dao.restoreVideo(bvId, DeviceTime.nowIsoString()) > 0
        if (restored) writeLog("info", "database", "视频已从回收站恢复", bvId)
        restored
    }

    /** Deletes the video row and every local snapshot atomically. Caller clears non-Room UI state after success. */
    suspend fun permanentlyDelete(bvId: String): Boolean = withContext(Dispatchers.IO) {
        val deleted = dao.permanentlyDeleteVideo(bvId)
        if (deleted) writeLog("warning", "database", "视频及历史记录已永久删除", bvId)
        deleted
    }

    suspend fun exportJson(bvId: String): ExportResult = withContext(Dispatchers.IO) {
        try {
            val video = dao.videoByBvId(bvId) ?: throw IllegalArgumentException("视频不存在")
            val snapshots = dao.snapshotsForExport(bvId).sortedWith(snapshotOldestFirst)
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
            val snapshots = dao.snapshotsForExport(bvId).sortedWith(snapshotOldestFirst)
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
        exporter.jsonPayload(video, dao.snapshotsForExport(bvId).sortedWith(snapshotOldestFirst))
    }

    suspend fun csvPayload(bvId: String): ExportPayload = withContext(Dispatchers.IO) {
        val video = dao.videoByBvId(bvId) ?: throw IllegalArgumentException("视频不存在")
        exporter.csvPayload(video, dao.snapshotsForExport(bvId).sortedWith(snapshotOldestFirst))
    }

    suspend fun exportHistoryExchange(sourceVersion: String): ByteArray = withContext(Dispatchers.IO) {
        HistoryExchangeCodec.export(
            dao.allVideosForExchange(),
            dao.allSnapshotsForExchange().sortedWith(compareBy<VideoSnapshotEntity> { it.bvId }.then(snapshotOldestFirst)),
            sourceVersion,
            deviceId
        )
    }

    suspend fun previewHistoryExchange(bytes: ByteArray): HistoryImportPreview = withContext(Dispatchers.IO) {
        HistoryExchangeCodec.preview(bytes)
    }

    suspend fun importHistoryExchange(packageData: HistoryExchangePackage): HistoryImportReport = withContext(Dispatchers.IO) {
        val report = dao.mergeHistoryExchange(packageData)
        writeLog("info", "exchange", "history exchange imported", "videos=${report.videosAdded}, snapshots=${report.snapshotsAdded}, duplicates=${report.duplicates}, conflicts=${report.conflicts}")
        report
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

    private companion object {
        val snapshotOldestFirst = Comparator<VideoSnapshotEntity> { left, right ->
            DeviceTime.compareAbsolute(left.collectedAt, right.collectedAt).takeIf { it != 0 }
                ?: left.id.compareTo(right.id)
        }
        val snapshotNewestFirst = snapshotOldestFirst.reversed()
    }
}
