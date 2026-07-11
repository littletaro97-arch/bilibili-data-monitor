package com.littletaro.bilibilimonitor.ui

data class AdvancedPageState(
    val showExportPanel: Boolean,
    val showEmptyExportMessage: Boolean
)

object AdvancedPageModel {
    fun from(selectedBvId: String?): AdvancedPageState {
        val hasSelection = !selectedBvId.isNullOrBlank()
        return AdvancedPageState(
            showExportPanel = hasSelection,
            showEmptyExportMessage = !hasSelection
        )
    }
}
