package com.littletaro.bilibilimonitor.data

object BvParser {
    private val bvPattern = Regex("""BV[0-9A-Za-z]{10}""")

    fun parse(input: String): String {
        val trimmed = input.trim()
        val match = bvPattern.find(trimmed)
        return match?.value ?: throw IllegalArgumentException("请输入有效的 BV 号或 Bilibili 视频链接")
    }
}
