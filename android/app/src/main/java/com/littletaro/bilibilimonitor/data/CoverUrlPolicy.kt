package com.littletaro.bilibilimonitor.data

import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

/** Accepts only public HTTPS image hosts used by Bilibili's CDN. */
object CoverUrlPolicy {
    fun acceptedOrNull(value: String?): String? {
        val url = value?.toHttpUrlOrNull() ?: return null
        val host = url.host.lowercase()
        return value.takeIf {
            url.isHttps && (host == "hdslb.com" || host.endsWith(".hdslb.com") ||
                host == "bilibili.com" || host.endsWith(".bilibili.com"))
        }
    }
}
