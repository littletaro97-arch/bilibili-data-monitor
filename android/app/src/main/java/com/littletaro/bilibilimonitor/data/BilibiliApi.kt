package com.littletaro.bilibilimonitor.data

import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.net.URI
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import java.util.concurrent.TimeUnit

class BilibiliApi(internal val client: OkHttpClient) {
    fun fetchSnapshot(bvId: String): VideoSnapshotRecord {
        val url = VIEW_URL.toHttpUrl().newBuilder()
            .addQueryParameter("bvid", bvId)
            .build()
        val request = Request.Builder()
            .url(url)
            .header("User-Agent", USER_AGENT)
            .header("Referer", "https://www.bilibili.com/")
            .build()

        try {
            client.newCall(request).execute().use { response ->
                if (response.code == 403) {
                    throw IOException("HTTP 403：访问被拒绝，可能触发平台限制")
                }
                if (response.code == 412) {
                    throw IOException("HTTP 412：请求被平台风控限制")
                }
                if (!response.isSuccessful) {
                    throw IOException("网络请求失败：HTTP ${response.code}")
                }
                val body = response.body?.string() ?: throw IOException("响应为空")
                return mapViewResponse(bvId, body, DeviceTime.nowIsoString())
            }
        } catch (exc: UnknownHostException) {
            throw IOException("无法连接网络或 DNS 解析失败，请检查网络", exc)
        } catch (exc: SocketTimeoutException) {
            throw IOException("请求超时，请稍后重试", exc)
        } catch (exc: JSONException) {
            throw IOException("接口返回内容无法解析，可能是 B 站接口结构变化", exc)
        }
    }

    companion object {
        private const val VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
        private const val USER_AGENT =
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        private const val MAX_REDIRECTS = 5

        fun resolveSharedBvId(input: String, client: OkHttpClient): String {
            val startUrl = BvParser.firstResolvableUrl(input)
                ?: throw IllegalArgumentException("未找到有效的哔哩哔哩视频链接")
            if (!BvParser.isBilibiliShortUrl(startUrl) && BvParser.isBilibiliUrl(startUrl)) {
                return BvParser.parse(startUrl)
            }
            val finalUrl = resolveRedirectTarget(startUrl, client)
            return BvParser.parse(finalUrl)
        }

        fun resolveRedirectTarget(startUrl: String, client: OkHttpClient): String {
            var current = startUrl
            val redirectClient = client.newBuilder()
                .followRedirects(false)
                .followSslRedirects(false)
                .callTimeout(10, TimeUnit.SECONDS)
                .build()
            repeat(MAX_REDIRECTS + 1) { step ->
                if (!BvParser.isBilibiliUrl(current) && !BvParser.isBilibiliShortUrl(current)) {
                    throw IOException("短链接跳转到了非哔哩哔哩地址")
                }
                val request = Request.Builder()
                    .url(current)
                    .header("User-Agent", USER_AGENT)
                    .build()
                try {
                    redirectClient.newCall(request).execute().use { response ->
                        if (response.isRedirect) {
                            if (step >= MAX_REDIRECTS) throw IOException("短链接跳转次数过多")
                            val location = response.header("Location")
                                ?: throw IOException("短链接跳转缺少目标地址")
                            current = resolveLocation(current, location)
                            return@repeat
                        }
                        if (!response.isSuccessful) {
                            throw IOException("短链接解析失败：HTTP ${response.code}")
                        }
                        return response.request.url.toString()
                    }
                } catch (exc: UnknownHostException) {
                    throw IOException("短链接解析失败，请检查网络", exc)
                } catch (exc: SocketTimeoutException) {
                    throw IOException("短链接解析超时，请稍后重试", exc)
                }
            }
            throw IOException("短链接解析失败：跳转次数过多")
        }

        private fun resolveLocation(baseUrl: String, location: String): String {
            val base = URI(baseUrl)
            return base.resolve(location).toString()
        }

        fun mapViewResponse(bvId: String, json: String, collectedAt: String): VideoSnapshotRecord {
            val root = JSONObject(json)
            val code = root.optInt("code", Int.MIN_VALUE)
            if (code != 0) {
                val message = root.optString("message", "接口返回失败")
                return failedRecord(bvId, collectedAt, classifyApiFailure(code, message))
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
                coverUrl = CoverUrlPolicy.acceptedOrNull(data.optNullableString("pic")),
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
                    coverUrl = null,
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

        private fun classifyApiFailure(code: Int, message: String): String {
            val normalized = message.lowercase()
            val hint = when {
                "login" in normalized || "登录" in message -> "接口要求登录，本应用不会绕过登录限制"
                "captcha" in normalized || "验证码" in message -> "接口要求验证码，本应用不会处理验证码"
                "risk" in normalized || "风控" in message -> "接口触发风控限制，本应用不会绕过"
                code == -404 -> "视频不存在或不可访问"
                else -> "接口返回失败"
            }
            return "$hint：code=$code, message=$message"
        }
    }
}

private fun JSONObject.optNullableString(name: String): String? =
    if (has(name) && !isNull(name)) optString(name) else null

private fun JSONObject.optNullableLong(name: String): Long? =
    if (has(name) && !isNull(name)) optLong(name) else null
