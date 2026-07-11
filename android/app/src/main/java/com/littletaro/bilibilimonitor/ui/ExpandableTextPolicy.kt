package com.littletaro.bilibilimonitor.ui

object ExpandableTextPolicy {
    fun shouldOfferExpansion(text: String): Boolean =
        text.length > 48 || text.contains('\n')
}
