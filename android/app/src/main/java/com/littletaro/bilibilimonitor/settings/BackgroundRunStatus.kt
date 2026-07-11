package com.littletaro.bilibilimonitor.settings

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.PowerManager
import android.provider.Settings

object BackgroundRunStatus {
    fun batteryOptimizationLabel(context: Context): String {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return "当前系统无需单独配置"
        val powerManager = context.getSystemService(PowerManager::class.java)
        return if (powerManager.isIgnoringBatteryOptimizations(context.packageName)) {
            "已允许不受电池优化限制"
        } else {
            "可能受系统电池优化限制"
        }
    }

    fun batteryOptimizationSettingsIntent(): Intent =
        Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)

    fun appSettingsIntent(context: Context): Intent =
        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
            .setData(android.net.Uri.parse("package:${context.packageName}"))
}
