package com.littletaro.bilibilimonitor.notifications

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.littletaro.bilibilimonitor.MainActivity
import com.littletaro.bilibilimonitor.data.RefreshAllResult
import com.littletaro.bilibilimonitor.settings.AutoRefreshSettings
import java.time.Instant

object MonitorNotificationManager {
    const val CHANNEL_ID = "bilibili_monitor_results"
    private const val NOTIFICATION_ID_REFRESH_SUMMARY = 2001

    fun permissionGranted(context: Context): Boolean {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
    }

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java)
        val existing = manager.getNotificationChannel(CHANNEL_ID)
        if (existing != null) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "监控结果提醒",
            NotificationManager.IMPORTANCE_DEFAULT
        ).apply {
            description = "显示 B站数据监控检测结果"
            enableVibration(true)
            lockscreenVisibility = android.app.Notification.VISIBILITY_PRIVATE
        }
        manager.createNotificationChannel(channel)
    }

    @SuppressLint("MissingPermission")
    fun maybeNotifyRefreshResult(
        context: Context,
        settings: AutoRefreshSettings,
        result: RefreshAllResult,
        now: Instant
    ): Boolean {
        if (result.total == 0) return false
        if (!MonitorNotificationPolicy.shouldSend(settings, permissionGranted(context), now)) return false
        ensureChannel(context)
        val detectedAt = now.toString()
        val body = MonitorNotificationPolicy.body(result, detectedAt)
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle(MonitorNotificationPolicy.title(result))
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(openAppPendingIntent(context))
            .setAutoCancel(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(NOTIFICATION_ID_REFRESH_SUMMARY, notification)
        } catch (_: SecurityException) {
            return false
        }
        return true
    }

    fun notificationSettingsIntent(context: Context): Intent {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
        } else {
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                .setData(android.net.Uri.parse("package:${context.packageName}"))
        }
    }

    private fun openAppPendingIntent(context: Context): PendingIntent {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        return PendingIntent.getActivity(
            context,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }
}
