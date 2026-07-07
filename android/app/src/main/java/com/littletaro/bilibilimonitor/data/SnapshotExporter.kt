package com.littletaro.bilibilimonitor.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.Instant

data class ExportResult(
    val fileName: String,
    val path: String,
    val exportedAt: String
)

class SnapshotExporter(context: Context) {
    private val exportDir: File = File(context.getExternalFilesDir(null), "exports").apply {
        mkdirs()
    }

    fun exportJson(video: VideoEntity, snapshots: List<VideoSnapshotEntity>): ExportResult {
        val exportedAt = Instant.now().toString()
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
        val target = File(exportDir, "${video.bvId}_${System.currentTimeMillis()}.json")
        target.writeText(root.toString(2), Charsets.UTF_8)
        return ExportResult(target.name, target.absolutePath, exportedAt)
    }

    fun exportCsv(video: VideoEntity, snapshots: List<VideoSnapshotEntity>): ExportResult {
        val exportedAt = Instant.now().toString()
        val target = File(exportDir, "${video.bvId}_${System.currentTimeMillis()}.csv")
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
        target.writeText(lines.joinToString("\n"), Charsets.UTF_8)
        return ExportResult(target.name, target.absolutePath, exportedAt)
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
