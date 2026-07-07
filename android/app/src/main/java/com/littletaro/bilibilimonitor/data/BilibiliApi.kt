package com.littletaro.bilibilimonitor.data

import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.IOException
import java.time.Instant

class BilibiliApi(private val client: OkHttpClient) {
    fun fetchSnapshot(bvId: String): VideoSnapshotRecord {
        val url = VIEW_URL.toHttpUrl().newBuilder()
            .addQueryParameter("bvid", bvId)
            .build()
        val request = Request.Builder()
            .url(url)
            .header("User-Agent", USER_AGENT)
            .header("Referer", "https://www.bilibili.com/")
            .build()

        client.newCall(request).execute().use { response ->
            if (response.code == 403 || response.code == 412) {
                throw IOException("请求被平台限制，HTTP ${response.code}")
            }
            if (!response.isSuccessful) {
                throw IOException("网络请求失败，HTTP ${response.code}")
            }
            val body = response.body?.string() ?: throw IOException("响应为空")
            return mapViewResponse(bvId, body, Instant.now().toString())
        }
    }

    companion object {
        private const val VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
        private const val USER_AGENT =
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

        fun mapViewResponse(bvId: String, json: String, collectedAt: String): VideoSnapshotRecord {
            val root = JSONObject(json)
            val code = root.optInt("code", Int.MIN_VALUE)
            if (code != 0) {
                val message = root.optString("message", "接口返回失败")
                return failedRecord(bvId, collectedAt, "接口返回失败：code=$code, message=$message")
            }
            val data = root.optJSONObject("data")
                ?: return failedRecord(bvId, collectedAt, "接口响应结构异常：缺少 data")
            val stat = data.optJSONObject("stat") ?: JSONObject()
            val owner = data.optJSONObject("owner") ?: JSONObject()
            val sourceUrl = "https://www.bilibili.com/video/$bvId/"
            val missingRequired = data.isNull("title") || stat.length() == 0
            val status = if (missingRequired) "partial" else "success"
            val error = if (missingRequired) "接口响应缺少部分字段" else null
            val video = VideoEntity(
                bvId = bvId,
                aid = data.optNullableLong("aid"),
                title = data.optNullableString("title"),
                authorName = owner.optNullableString("name"),
                authorMid = owner.optNullableLong("mid"),
                duration = data.optNullableLong("duration"),
                pubdate = data.optNullableLong("pubdate"),
                sourceUrl = sourceUrl,
                createdAt = collectedAt,
                updatedAt = collectedAt
            )
            val snapshot = VideoSnapshotEntity(
                bvId = bvId,
                collectedAt = collectedAt,
                viewCount = stat.optNullableLong("view"),
                danmakuCount = stat.optNullableLong("danmaku"),
                replyCount = stat.optNullableLong("reply"),
                favoriteCount = stat.optNullableLong("favorite"),
                coinCount = stat.optNullableLong("coin"),
                shareCount = stat.optNullableLong("share"),
                likeCount = stat.optNullableLong("like"),
                sourceUrl = sourceUrl,
                fetchStatus = status,
                errorMessage = error
            )
            return VideoSnapshotRecord(video, snapshot)
        }

        private fun failedRecord(bvId: String, collectedAt: String, message: String): VideoSnapshotRecord {
            val sourceUrl = "https://www.bilibili.com/video/$bvId/"
            return VideoSnapshotRecord(
                video = VideoEntity(
                    bvId = bvId,
                    aid = null,
                    title = null,
                    authorName = null,
                    authorMid = null,
                    duration = null,
                    pubdate = null,
                    sourceUrl = sourceUrl,
                    createdAt = collectedAt,
                    updatedAt = collectedAt
                ),
                snapshot = VideoSnapshotEntity(
                    bvId = bvId,
                    collectedAt = collectedAt,
                    viewCount = null,
                    danmakuCount = null,
                    replyCount = null,
                    favoriteCount = null,
                    coinCount = null,
                    shareCount = null,
                    likeCount = null,
                    sourceUrl = sourceUrl,
                    fetchStatus = "failed",
                    errorMessage = message
                )
            )
        }
    }
}

private fun JSONObject.optNullableString(name: String): String? =
    if (has(name) && !isNull(name)) optString(name) else null

private fun JSONObject.optNullableLong(name: String): Long? =
    if (has(name) && !isNull(name)) optLong(name) else null
