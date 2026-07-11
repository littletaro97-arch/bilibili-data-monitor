package com.littletaro.bilibilimonitor.ui

object WheelEditorPolicy {
    @JvmStatic
    fun defaultExpanded(): Boolean = false

    @JvmStatic
    fun toggle(expanded: Boolean): Boolean = !expanded

    @JvmStatic
    fun complete(): Boolean = false

    @JvmStatic
    fun summary(title: String, selectedLabel: String, enabledLabel: String): String =
        "$title $selectedLabel $enabledLabel"
}
