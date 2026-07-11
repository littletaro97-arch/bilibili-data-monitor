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
    private const val NOTIFICATION_ID_TEST = 2002

    enum class SendResult(val value: String) {
        SENT("已发送"), PERMISSION_DENIED("权限未开启"), CHANNEL_DISABLED("通知渠道关闭"),
        INTERVAL_NOT_REACHED("未达到通知间隔"), NO_RESULT("没有新的检测结果"),
        DISABLED("程序内通知已关闭"), FAILED("发送失败")
    }

    fun permissionGranted(context: Context): Boolean {
        val runtimeGranted = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        return runtimeGranted && NotificationManagerCompat.from(context).areNotificationsEnabled()
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

    fun channelEnabled(context: Context): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return true
        ensureChannel(context)
        return context.getSystemService(NotificationManager::class.java)
            .getNotificationChannel(CHANNEL_ID)?.importance != NotificationManager.IMPORTANCE_NONE
    }

    @SuppressLint("MissingPermission")
    fun maybeNotifyRefreshResult(
        context: Context,
        settings: AutoRefreshSettings,
        result: RefreshAllResult,
        now: Instant
    ): SendResult {
        if (!settings.notificationsEnabled) return SendResult.DISABLED
        if (!permissionGranted(context)) return SendResult.PERMISSION_DENIED
        if (result.total == 0 || result.success == 0) return SendResult.NO_RESULT
        ensureChannel(context)
        if (!channelEnabled(context)) return SendResult.CHANNEL_DISABLED
        if (!MonitorNotificationPolicy.shouldSend(settings, true, now)) return SendResult.INTERVAL_NOT_REACHED
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
        } catch (_: Exception) {
            return SendResult.FAILED
        }
        return SendResult.SENT
    }

    @SuppressLint("MissingPermission")
    fun sendTestNotification(context: Context): SendResult {
        if (!permissionGranted(context)) return SendResult.PERMISSION_DENIED
        ensureChannel(context)
        if (!channelEnabled(context)) return SendResult.CHANNEL_DISABLED
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle("B站数据监控测试通知")
            .setContentText("通知权限与通知渠道工作正常")
            .setContentIntent(openAppPendingIntent(context))
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()
        return try {
            NotificationManagerCompat.from(context).notify(NOTIFICATION_ID_TEST, notification)
            SendResult.SENT
        } catch (_: Exception) {
            SendResult.FAILED
        }
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
