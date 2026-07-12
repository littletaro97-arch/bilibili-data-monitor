package com.littletaro.bilibilimonitor.ui

import com.littletaro.bilibilimonitor.data.HistoryImportReport

enum class BackAction { CLOSE_OVERLAY, GO_HOME, SYSTEM_DEFAULT }

object NavigationBackPolicy {
    fun action(hasOverlay: Boolean, isHome: Boolean): BackAction = when {
        hasOverlay -> BackAction.CLOSE_OVERLAY
        !isHome -> BackAction.GO_HOME
        else -> BackAction.SYSTEM_DEFAULT
    }
}

object HistoryImportFeedback {
    fun isComplete(report: HistoryImportReport): Boolean = report.conflicts == 0 && report.invalid == 0

    fun message(report: HistoryImportReport): String = buildString {
        append("新增 ${report.videosAdded} 个视频、${report.snapshotsAdded} 条历史记录，跳过 ${report.duplicates} 条重复数据。")
        val skipped = report.conflicts + report.invalid
        if (skipped > 0) append("\n另有 $skipped 条数据未导入。")
    }
}

object HistoryExpansionPolicy {
    fun stateKey(snapshotId: Long): Long = snapshotId
    fun defaultExpanded(): Boolean = false
}
