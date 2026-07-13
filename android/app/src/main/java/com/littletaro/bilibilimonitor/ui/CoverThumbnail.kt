package com.littletaro.bilibilimonitor.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import com.littletaro.bilibilimonitor.data.CoverUrlPolicy
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

@Composable
internal fun CoverThumbnail(url: String?, modifier: Modifier = Modifier) {
    val context = LocalContext.current.applicationContext
    val bitmap by produceState<Bitmap?>(initialValue = null, url) {
        value = withContext(Dispatchers.IO) { CoverBitmapCache.load(context.cacheDir, url) }
    }
    Box(
        modifier = modifier.background(MaterialTheme.colorScheme.surfaceContainerHighest),
        contentAlignment = Alignment.Center
    ) {
        if (bitmap != null) {
            Image(
                bitmap = bitmap!!.asImageBitmap(),
                contentDescription = "视频封面",
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize()
            )
        } else {
            Text(
                text = "暂无封面",
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.labelSmall
            )
        }
    }
}

private object CoverBitmapCache {
    private const val MAX_MEMORY_BYTES = 8 * 1024 * 1024
    private const val MAX_DISK_BYTES = 24L * 1024 * 1024
    private const val MAX_DOWNLOAD_BYTES = 2L * 1024 * 1024
    private const val TARGET_WIDTH = 320
    private const val TARGET_HEIGHT = 180
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .build()
    private val memory = object : LruCache<String, Bitmap>(MAX_MEMORY_BYTES) {
        override fun sizeOf(key: String, value: Bitmap): Int = value.allocationByteCount
    }

    fun load(cacheRoot: File, url: String?): Bitmap? {
        val safeUrl = CoverUrlPolicy.acceptedOrNull(url) ?: return null
        memory.get(safeUrl)?.let { return it }
        val directory = File(cacheRoot, "bilibili-covers").apply { mkdirs() }
        val target = File(directory, sha256(safeUrl) + ".img")
        val bytes = readBounded(target) ?: download(safeUrl)?.also { writeAtomically(target, it) } ?: return null
        val bitmap = decodeScaled(bytes) ?: run {
            target.delete()
            return null
        }
        memory.put(safeUrl, bitmap)
        target.setLastModified(System.currentTimeMillis())
        trimDisk(directory)
        return bitmap
    }

    private fun download(url: String): ByteArray? = runCatching {
        val request = Request.Builder().url(url).header("User-Agent", "BilibiliMonitor/1.0").build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful || response.body == null ||
                response.body!!.contentLength() > MAX_DOWNLOAD_BYTES
            ) return null
            response.body!!.byteStream().use { input ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    if (output.size().toLong() + count > MAX_DOWNLOAD_BYTES) return null
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
        }
    }.getOrNull()

    private fun decodeScaled(bytes: ByteArray): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
        var sample = 1
        while (bounds.outWidth / sample > TARGET_WIDTH * 2 || bounds.outHeight / sample > TARGET_HEIGHT * 2) sample *= 2
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply {
            inSampleSize = sample
            inPreferredConfig = Bitmap.Config.RGB_565
        })
    }

    private fun readBounded(file: File): ByteArray? =
        if (file.isFile && file.length() in 1..MAX_DOWNLOAD_BYTES) file.readBytes() else null

    private fun writeAtomically(target: File, bytes: ByteArray) {
        val temporary = File(target.parentFile, target.name + ".tmp")
        runCatching {
            FileOutputStream(temporary).use { it.write(bytes) }
            if (!temporary.renameTo(target)) {
                target.delete()
                temporary.renameTo(target)
            }
        }
        temporary.delete()
    }

    private fun trimDisk(directory: File) {
        var total = directory.listFiles()?.sumOf { it.length() } ?: 0L
        directory.listFiles()?.sortedBy { it.lastModified() }?.forEach { file ->
            if (total <= MAX_DISK_BYTES) return
            total -= file.length()
            file.delete()
        }
    }

    private fun sha256(value: String): String =
        MessageDigest.getInstance("SHA-256").digest(value.toByteArray()).joinToString("") { "%02x".format(it) }
}
