package com.littletaro.bilibilimonitor.navigation

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build

data class VideoOpenAttempt(
    val stage: String,
    val packageRestricted: Boolean,
    val succeeded: Boolean,
    val exceptionType: String? = null
)

data class VideoOpenResult(
    val succeeded: Boolean,
    val uri: String,
    val attempts: List<VideoOpenAttempt>
) {
    val errorMessage: String? = if (succeeded) null else "未找到可以打开该视频链接的应用"
    fun logDetail(): String = buildString {
        append("uri=").append(uri).append(", android=").append(Build.VERSION.SDK_INT)
        attempts.forEach { attempt ->
            append(", ").append(attempt.stage)
                .append("{packageRestricted=").append(attempt.packageRestricted)
                .append(", success=").append(attempt.succeeded)
                .append(", exception=").append(attempt.exceptionType ?: "none").append('}')
        }
    }
}

interface VideoIntentStarter {
    fun start(uri: String, packageName: String?): VideoOpenAttempt
}

class AndroidVideoIntentStarter(private val context: Context) : VideoIntentStarter {
    override fun start(uri: String, packageName: String?): VideoOpenAttempt {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(uri)).apply {
            packageName?.let(::setPackage)
            if (context !is Activity) addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        val stage = if (packageName == null) "generic_https" else "bilibili_app"
        return try {
            context.startActivity(intent)
            VideoOpenAttempt(stage, packageName != null, true)
        } catch (exc: ActivityNotFoundException) {
            VideoOpenAttempt(stage, packageName != null, false, exc.javaClass.simpleName)
        } catch (exc: SecurityException) {
            VideoOpenAttempt(stage, packageName != null, false, exc.javaClass.simpleName)
        } catch (exc: RuntimeException) {
            VideoOpenAttempt(stage, packageName != null, false, exc.javaClass.simpleName)
        }
    }
}

class VideoLinkOpener(private val starter: VideoIntentStarter) {
    fun open(bvId: String): VideoOpenResult {
        require(BV_PATTERN.matches(bvId)) { "无效 BV 号" }
        val uri = "https://www.bilibili.com/video/$bvId"
        val directed = starter.start(uri, BILIBILI_PACKAGE)
        if (directed.succeeded) return VideoOpenResult(true, uri, listOf(directed))
        val generic = starter.start(uri, null)
        return VideoOpenResult(generic.succeeded, uri, listOf(directed, generic))
    }

    companion object {
        const val BILIBILI_PACKAGE = "tv.danmaku.bili"
        private val BV_PATTERN = Regex("^BV[0-9A-Za-z]{10}$")
    }
}
