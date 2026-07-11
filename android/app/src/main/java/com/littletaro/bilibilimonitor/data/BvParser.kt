package com.littletaro.bilibilimonitor.data

import java.net.URI

object BvParser {
    private val bvPattern = Regex("""(?i)\bBV[0-9A-Za-z]{10}\b""")
    private val urlPattern = Regex("""https?://[^\s<>"'，。！？；：、]+""")
    private val trailingPunctuation = "，。！？；：、,.!?;:)）]】》」』"

    fun parse(input: String): String {
        val match = bvPattern.find(normalize(input))
        return match?.value?.let { normalizeBvPrefix(it) }
            ?: throw IllegalArgumentException("未找到有效的哔哩哔哩视频链接")
    }

    fun extractUrls(input: String): List<String> =
        urlPattern.findAll(normalize(input))
            .map { it.value.trimTrailingPunctuation() }
            .filter { it.isNotBlank() }
            .toList()

    fun firstResolvableUrl(input: String): String? =
        extractUrls(input).firstOrNull { isBilibiliUrl(it) || isBilibiliShortUrl(it) }

    fun isBilibiliUrl(url: String): Boolean =
        runCatching {
            val host = URI(url).host?.lowercase() ?: return@runCatching false
            host == "bilibili.com" || host.endsWith(".bilibili.com")
        }.getOrDefault(false)

    fun isBilibiliShortUrl(url: String): Boolean =
        runCatching {
            val host = URI(url).host?.lowercase() ?: return@runCatching false
            host == "b23.tv" ||
                host == "bili22.cn" ||
                host == "bili23.cn" ||
                host == "bili33.cn" ||
                host == "bili2233.cn"
        }.getOrDefault(false)

    private fun normalize(input: String): String =
        input.trim()
            .replace('\u3000', ' ')
            .replace('？', '?')
            .replace('＆', '&')
            .replace('＝', '=')

    private fun normalizeBvPrefix(value: String): String =
        "BV" + value.drop(2)

    private fun String.trimTrailingPunctuation(): String =
        trim().trimEnd { it in trailingPunctuation }
}
