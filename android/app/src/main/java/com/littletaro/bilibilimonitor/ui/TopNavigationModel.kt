package com.littletaro.bilibilimonitor.ui

object TopNavigationModel {
    fun labels(hasSelection: Boolean): List<String> =
        if (hasSelection) {
            listOf("首页", "回收站", "详情", "历史", "设置", "高级")
        } else {
            listOf("首页", "回收站", "设置", "高级")
        }

    fun resolveSelection(selectedBvId: String?, existingBvIds: List<String>): String? =
        selectedBvId?.takeIf { it in existingBvIds }
}
