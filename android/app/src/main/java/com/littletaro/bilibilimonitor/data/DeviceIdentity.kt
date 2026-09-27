package com.littletaro.bilibilimonitor.data

import android.content.Context
import java.util.UUID

/** A non-secret installation identifier used only to make synced snapshots idempotent. */
object DeviceIdentity {
    private const val PREFERENCES = "device_identity"
    private const val KEY_DEVICE_ID = "device_id"

    fun get(context: Context): String {
        val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
        val existing = preferences.getString(KEY_DEVICE_ID, null)
        if (!existing.isNullOrBlank()) return existing
        return UUID.randomUUID().toString().also {
            check(preferences.edit().putString(KEY_DEVICE_ID, it).commit()) { "无法保存设备标识" }
        }
    }
}
