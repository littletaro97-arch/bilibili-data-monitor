package com.littletaro.bilibilimonitor.data

import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.security.MessageDigest
import java.time.Instant
import java.util.UUID
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

data class HistoryExchangePackage(
    val sourcePlatform: String,
    val exportedAt: String,
    val videos: List<VideoEntity>,
    val snapshots: List<VideoSnapshotEntity>
)

data class HistoryImportPreview(
    val sourcePlatform: String,
    val exportedAt: String,
    val videoCount: Int,
    val snapshotCount: Int,
    val packageData: HistoryExchangePackage
)

data class HistoryImportReport(
    val videosAdded: Int,
    val snapshotsAdded: Int,
    val duplicates: Int,
    val conflicts: Int,
    val invalid: Int = 0
)

object HistoryExchangeCodec {
    const val FORMAT_NAME = "bilibili-history-exchange"
    const val FORMAT_VERSION = 1
    const val MAX_ZIP_BYTES = 100L * 1024 * 1024
    const val MAX_TOTAL_UNCOMPRESSED = 200L * 1024 * 1024
    const val MAX_JSON_BYTES = 100L * 1024 * 1024
    const val MAX_ENTRIES = 8
    const val MAX_COMPRESSION_RATIO = 100L
    private val requiredEntries = setOf("manifest.json", "videos.json", "snapshots.json", "checksums.json")

    fun export(videos: List<VideoEntity>, snapshots: List<VideoSnapshotEntity>, sourceVersion: String): ByteArray {
        val exportedAt = Instant.now().toString()
        val videosBytes = videosJson(videos).toString().toByteArray(Charsets.UTF_8)
        val snapshotsBytes = snapshotsJson(snapshots).toString().toByteArray(Charsets.UTF_8)
        val manifestBytes = JSONObject()
            .put("formatName", FORMAT_NAME)
            .put("formatVersion", FORMAT_VERSION)
            .put("exportId", UUID.randomUUID().toString())
            .put("exportedAt", exportedAt)
            .put("sourcePlatform", "android")
            .put("sourceAppVersion", sourceVersion)
            .put("schemaVersion", 4)
            .put("recordCounts", JSONObject().put("videos", videos.size).put("snapshots", snapshots.size))
            .put("includedSections", JSONArray(listOf("videos", "snapshots")))
            .put("timeStandard", "UTC RFC3339")
            .put("checksumAlgorithm", "SHA-256")
            .toString().toByteArray(Charsets.UTF_8)
        val checksumsBytes = JSONObject()
            .put("manifest.json", sha256(manifestBytes))
            .put("videos.json", sha256(videosBytes))
            .put("snapshots.json", sha256(snapshotsBytes))
            .toString().toByteArray(Charsets.UTF_8)
        val files = linkedMapOf(
            "manifest.json" to manifestBytes,
            "videos.json" to videosBytes,
            "snapshots.json" to snapshotsBytes,
            "checksums.json" to checksumsBytes
        )
        return ByteArrayOutputStream().use { output ->
            ZipOutputStream(output).use { zip ->
                files.forEach { (name, bytes) ->
                    zip.putNextEntry(ZipEntry(name))
                    zip.write(bytes)
                    zip.closeEntry()
                }
            }
            output.toByteArray()
        }
    }

    fun preview(bytes: ByteArray): HistoryImportPreview {
        require(bytes.size <= MAX_ZIP_BYTES) { "ZIP 超过 100MB 限制" }
        require(bytes.size >= 4 && bytes[0] == 0x50.toByte() && bytes[1] == 0x4b.toByte()) { "文件不是有效 ZIP" }
        val files = readZip(bytes)
        require(files.keys == requiredEntries) { "ZIP 文件结构不符合交换格式" }
        val checksums = JSONObject(files.getValue("checksums.json").toString(Charsets.UTF_8))
        listOf("manifest.json", "videos.json", "snapshots.json").forEach { name ->
            require(checksums.optString(name) == sha256(files.getValue(name))) { "$name SHA-256 校验失败" }
        }
        val manifest = JSONObject(files.getValue("manifest.json").toString(Charsets.UTF_8))
        require(manifest.optString("formatName") == FORMAT_NAME) { "未知交换格式" }
        require(manifest.optInt("formatVersion", -1) == FORMAT_VERSION) { "不支持的 formatVersion" }
        val videos = parseVideos(JSONArray(files.getValue("videos.json").toString(Charsets.UTF_8)))
        val snapshots = parseSnapshots(JSONArray(files.getValue("snapshots.json").toString(Charsets.UTF_8)))
        val counts = manifest.getJSONObject("recordCounts")
        require(counts.getInt("videos") == videos.size && counts.getInt("snapshots") == snapshots.size) { "记录数量与 manifest 不一致" }
        val data = HistoryExchangePackage(manifest.getString("sourcePlatform"), manifest.getString("exportedAt"), videos, snapshots)
        return HistoryImportPreview(data.sourcePlatform, data.exportedAt, videos.size, snapshots.size, data)
    }

    fun snapshotDigest(snapshot: VideoSnapshotEntity): String = sha256(
        listOf(
            snapshot.bvId, normalizeTime(snapshot.collectedAt), SnapshotSources.sanitize(snapshot.captureSource),
            snapshot.viewCount, snapshot.danmakuCount, snapshot.replyCount, snapshot.favoriteCount,
            snapshot.coinCount, snapshot.shareCount, snapshot.likeCount, snapshot.fetchStatus, snapshot.errorMessage
        ).joinToString("\u001f") { it?.toString() ?: "null" }.toByteArray(Charsets.UTF_8)
    )

    private fun readZip(bytes: ByteArray): Map<String, ByteArray> {
        val result = linkedMapOf<String, ByteArray>()
        var total = 0L
        ZipInputStream(ByteArrayInputStream(bytes)).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                val name = entry.name
                require(!entry.isDirectory && name in requiredEntries && !name.contains("..") && !name.startsWith('/') && !name.contains('\\')) { "ZIP 包含非法条目" }
                require(name !in result && result.size < MAX_ENTRIES) { "ZIP 条目重复或过多" }
                val out = ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                var count: Int
                while (zip.read(buffer).also { count = it } >= 0) {
                    if (count == 0) continue
                    out.write(buffer, 0, count)
                    total += count
                    require(out.size().toLong() <= MAX_JSON_BYTES && total <= MAX_TOTAL_UNCOMPRESSED) { "ZIP 解压大小超过限制" }
                }
                val compressed = entry.compressedSize
                if (compressed > 0) require(out.size().toLong() / compressed.coerceAtLeast(1) <= MAX_COMPRESSION_RATIO) { "ZIP 压缩比异常" }
                result[name] = out.toByteArray()
                zip.closeEntry()
            }
        }
        return result
    }

    private fun videosJson(videos: List<VideoEntity>) = JSONArray().apply {
        videos.forEach { video -> put(JSONObject().put("bvId", video.bvId).put("aid", video.aid).put("title", video.title).put("authorName", video.authorName).put("authorMid", video.authorMid).put("duration", video.duration).put("pubdate", video.pubdate).put("coverUrl", video.coverUrl).put("sourceUrl", video.sourceUrl)) }
    }

    private fun snapshotsJson(snapshots: List<VideoSnapshotEntity>) = JSONArray().apply {
        snapshots.forEach { snapshot -> put(JSONObject().put("bvId", snapshot.bvId).put("collectedAt", normalizeTime(snapshot.collectedAt)).put("collectionSource", SnapshotSources.sanitize(snapshot.captureSource)).put("viewCount", snapshot.viewCount).put("danmakuCount", snapshot.danmakuCount).put("replyCount", snapshot.replyCount).put("favoriteCount", snapshot.favoriteCount).put("coinCount", snapshot.coinCount).put("shareCount", snapshot.shareCount).put("likeCount", snapshot.likeCount).put("fetchStatus", snapshot.fetchStatus).put("errorMessage", snapshot.errorMessage).put("contentSha256", snapshotDigest(snapshot))) }
    }

    private fun parseVideos(array: JSONArray): List<VideoEntity> = (0 until array.length()).map { index ->
        val item = array.getJSONObject(index)
        val bv = item.getString("bvId")
        require(Regex("^BV[0-9A-Za-z]{10}$").matches(bv)) { "videos.json 包含无效 BV" }
        VideoEntity(bv, item.optLongOrNull("aid"), item.optNullableString("title"), item.optNullableString("authorName"), item.optLongOrNull("authorMid"), item.optLongOrNull("duration"), item.optLongOrNull("pubdate"), CoverUrlPolicy.acceptedOrNull(item.optNullableString("coverUrl")), item.optNullableString("sourceUrl"), Instant.now().toString(), Instant.now().toString())
    }

    private fun parseSnapshots(array: JSONArray): List<VideoSnapshotEntity> = (0 until array.length()).map { index ->
        val item = array.getJSONObject(index)
        val source = SnapshotSources.sanitize(item.getString("collectionSource"))
        val snapshot = VideoSnapshotEntity(bvId = item.getString("bvId"), collectedAt = normalizeTime(item.getString("collectedAt")), viewCount = item.optLongOrNull("viewCount"), danmakuCount = item.optLongOrNull("danmakuCount"), replyCount = item.optLongOrNull("replyCount"), favoriteCount = item.optLongOrNull("favoriteCount"), coinCount = item.optLongOrNull("coinCount"), shareCount = item.optLongOrNull("shareCount"), likeCount = item.optLongOrNull("likeCount"), sourceUrl = null, fetchStatus = item.getString("fetchStatus"), errorMessage = item.optNullableString("errorMessage"), captureSource = source, exchangeDigest = item.getString("contentSha256"))
        require(snapshot.exchangeDigest == snapshotDigest(snapshot)) { "snapshots.json 内容摘要不匹配" }
        snapshot
    }

    private fun normalizeTime(value: String): String = DeviceTime.parseToInstant(value)?.toString() ?: throw IllegalArgumentException("无效 UTC 时间")
    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    private fun JSONObject.optLongOrNull(name: String): Long? = if (!has(name) || isNull(name)) null else getLong(name).also { require(it >= 0) { "$name 不能为负数" } }
    private fun JSONObject.optNullableString(name: String): String? = if (!has(name) || isNull(name)) null else getString(name)
}
