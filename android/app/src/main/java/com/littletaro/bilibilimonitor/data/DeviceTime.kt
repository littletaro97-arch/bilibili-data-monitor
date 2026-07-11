package com.littletaro.bilibilimonitor.data

import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.time.temporal.ChronoUnit

object DeviceTime {
    private val displayFormatter: DateTimeFormatter =
        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")

    @JvmStatic
    fun nowIsoString(): String =
        Instant.now().truncatedTo(ChronoUnit.SECONDS).toString()

    @JvmStatic
    fun nowInstant(): Instant = Instant.now()

    @JvmStatic
    fun formatForDisplay(value: String?): String {
        if (value.isNullOrBlank()) return "-"
        val instant = parseToInstant(value) ?: return value
        return displayFormatter.format(instant.atZone(ZoneId.systemDefault()))
    }

    @JvmStatic
    fun parseToInstant(value: String?): Instant? {
        if (value.isNullOrBlank()) return null
        return try {
            Instant.parse(value)
        } catch (_: DateTimeParseException) {
            try {
                OffsetDateTime.parse(value).toInstant()
            } catch (_: DateTimeParseException) {
                null
            }
        }
    }

    @JvmStatic
    fun compareAbsolute(left: String?, right: String?): Int {
        val leftInstant = parseToInstant(left)
        val rightInstant = parseToInstant(right)
        return when {
            leftInstant != null && rightInstant != null -> leftInstant.compareTo(rightInstant)
            leftInstant != null -> 1
            rightInstant != null -> -1
            else -> (left ?: "").compareTo(right ?: "")
        }
    }
}
