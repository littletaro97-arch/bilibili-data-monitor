package com.littletaro.bilibilimonitor.data

import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

object ExportFileNamer {
    private val TIME_FORMATTER: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss")
    private val ILLEGAL_CHARS = Regex("[\\\\/:*?\"<>|\\r\\n\\t]+")

    fun build(bvId: String, title: String?, typeLabel: String, extension: String): String {
        val safeTitle = title
            ?.replace(ILLEGAL_CHARS, "_")
            ?.trim()
            ?.take(32)
            ?.takeIf { it.isNotBlank() }
        val titlePart = safeTitle?.let { "_$it" } ?: ""
        return "${bvId}${titlePart}_${typeLabel}_${LocalDateTime.now().format(TIME_FORMATTER)}.$extension"
    }
}
