package com.littletaro.bilibilimonitor.ui

object ExportLocationPolicy {
    fun shouldLaunchPicker(defaultTreeUri: String?, askEveryTime: Boolean, forcePicker: Boolean): Boolean =
        forcePicker || askEveryTime || defaultTreeUri.isNullOrBlank()
}
