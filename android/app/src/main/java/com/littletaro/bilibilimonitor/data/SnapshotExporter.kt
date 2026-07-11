package com.littletaro.bilibilimonitor.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

data class ExportResult(
    val fileName: String,
    val path: String,
    val exportedAt: String,
    val sizeBytes: Long
)

data class ExportPayload(
    val fileName: String,
    val mimeType: String,
    val content: String,
    val exportedAt: String
) {
    val sizeBytes: Long = content.toByteArray(Charsets.UTF_8).size.toLong()
}

class SnapshotExporter(context: Context) {
    private val exportDir: File = File(context.getExternalFilesDir(null), "exports").apply {
        mkdirs()
    }

    fun exportJson(video: VideoEntity, snapshots: List<VideoSnapshotEntity>): ExportResult {
        val payload = jsonPayload(video, snapshots)
        val target = File(exportDir, payload.fileName)
        target.writeText(payload.content, Charsets.UTF_8)
        return ExportResult(target.name, target.absolutePath, payload.exportedAt, target.length())
    }

    fun exportCsv(video: VideoEntity, snapshots: List<VideoSnapshotEntity>): ExportResult {
        val payload = csvPayload(video, snapshots)
        val target = File(exportDir, payload.fileName)
        target.writeText(payload.content, Charsets.UTF_8)
        return ExportResult(target.name, target.absolutePath, payload.exportedAt, target.length())
    }

    fun jsonPayload(video: VideoEntity, snapshots: List<VideoSnapshotEntity>): ExportPayload {
        val exportedAt = DeviceTime.nowIsoString()
        val root = JSONObject()
            .put("platform", "bilibili")
            .put("bv_id", video.bvId)
            .put("aid", video.aid)
            .put("title", video.title)
            .put("author_name", video.authorName)
            .put("author_mid", video.authorMid)
            .put("source_url", video.sourceUrl)
            .put("exported_at", exportedAt)
            .put("snapshots", JSONArray().also { array ->
                snapshots.forEach { array.put(snapshotJson(video, it)) }
            })
        return ExportPayload(
            fileName = ExportFileNamer.build(video.bvId, video.title, "历史数据", "json"),
            mimeType = "application/json",
            content = root.toString(2),
            exportedAt = exportedAt
        )
    }

    fun csvPayload(video: VideoEntity, snapshots: List<VideoSnapshotEntity>): ExportPayload {
        val exportedAt = DeviceTime.nowIsoString()
        val lines = buildList {
            add(CSV_HEADER.joinToString(","))
            snapshots.forEach { snapshot ->
                add(
                    listOf(
                        "bilibili",
                        video.bvId,
                        video.aid,
                        video.title,
                        video.authorName,
                        video.authorMid,
                        video.duration,
                        video.pubdate,
                        snapshot.collectedAt,
                        snapshot.viewCount,
                        snapshot.danmakuCount,
                        snapshot.replyCount,
                        snapshot.favoriteCount,
                        snapshot.coinCount,
                        snapshot.shareCount,
                        snapshot.likeCount,
                        snapshot.sourceUrl,
                        snapshot.fetchStatus,
                        snapshot.errorMessage
                    ).joinToString(",") { csvCell(it) }
                )
            }
        }
        return ExportPayload(
            fileName = ExportFileNamer.build(video.bvId, video.title, "历史数据", "csv"),
            mimeType = "text/csv",
            content = lines.joinToString("\n"),
            exportedAt = exportedAt
        )
    }

    companion object {
        val CSV_HEADER = listOf(
            "platform",
            "bv_id",
            "aid",
            "title",
            "author_name",
            "author_mid",
            "duration",
            "pubdate",
            "collected_at",
            "view_count",
            "danmaku_count",
            "reply_count",
            "favorite_count",
            "coin_count",
            "share_count",
            "like_count",
            "source_url",
            "fetch_status",
            "error_message"
        )

        fun csvCell(value: Any?): String {
            val raw = value?.toString() ?: ""
            val escaped = raw.replace("\"", "\"\"")
            return if (escaped.any { it == ',' || it == '"' || it == '\n' || it == '\r' }) {
                "\"$escaped\""
            } else {
                escaped
            }
        }

        fun snapshotJson(video: VideoEntity, snapshot: VideoSnapshotEntity): JSONObject =
            JSONObject()
                .put("platform", "bilibili")
                .put("bv_id", video.bvId)
                .put("aid", video.aid)
                .put("title", video.title)
                .put("author_name", video.authorName)
                .put("author_mid", video.authorMid)
                .put("duration", video.duration)
                .put("pubdate", video.pubdate)
                .put("collected_at", snapshot.collectedAt)
                .put("view_count", snapshot.viewCount)
                .put("danmaku_count", snapshot.danmakuCount)
                .put("reply_count", snapshot.replyCount)
                .put("favorite_count", snapshot.favoriteCount)
                .put("coin_count", snapshot.coinCount)
                .put("share_count", snapshot.shareCount)
                .put("like_count", snapshot.likeCount)
                .put("source_url", snapshot.sourceUrl)
                .put("fetch_status", snapshot.fetchStatus)
                .put("error_message", snapshot.errorMessage)
    }
}
