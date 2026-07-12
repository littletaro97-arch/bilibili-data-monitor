package com.littletaro.bilibilimonitor.worker

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import com.littletaro.bilibilimonitor.BilibiliMonitorApplication
import com.littletaro.bilibilimonitor.MainActivity
import com.littletaro.bilibilimonitor.data.DeviceTime
import com.littletaro.bilibilimonitor.data.RefreshTrigger
import com.littletaro.bilibilimonitor.notifications.MonitorNotificationManager
import com.littletaro.bilibilimonitor.settings.RefreshIntervals
import com.littletaro.bilibilimonitor.settings.CheckStates
import com.littletaro.bilibilimonitor.settings.MonitoringRuntime
import com.littletaro.bilibilimonitor.settings.ScheduleModes
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class ContinuousMonitoringService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var loopJob: Job? = null
    private val app by lazy { application as BilibiliMonitorApplication }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val reconfiguring = intent?.action == ACTION_RECONFIGURE
        if (intent?.action == ACTION_STOP) {
            stopWithResult("stopped by user", disablePreference = true)
            return START_NOT_STICKY
        }
        if (intent?.action == ACTION_STOP_FOR_RECONFIGURE) {
            stopWithResult("stopped for schedule change", restorePeriodic = false)
            return START_NOT_STICKY
        }
        if (reconfiguring) {
            loopJob?.cancel()
            loopJob = null
        } else if (loopJob?.isActive == true) return START_NOT_STICKY
        if (!MonitorNotificationManager.permissionGranted(this) || !channelEnabled()) {
            stopWithResult("notification permission or channel unavailable")
            return START_NOT_STICKY
        }
        if (!reconfiguring) startForegroundNotification(null)
        launchLoop()
        return START_NOT_STICKY
    }

    private fun launchLoop() {
        loopJob = scope.launch {
            val settings = app.settingsStore.settings.first()
            if (!settings.enabled || !settings.continuousMonitoringEnabled || settings.intervalMinutes >= RefreshIntervals.MIN_WORK_MANAGER_MINUTES) {
                stopWithResult("invalid continuous monitoring settings")
                return@launch
            }
            startForegroundNotification(settings.intervalMinutes)
            app.autoRefreshScheduler.cancelAndAwait()
            app.settingsStore.recordCancelled(DeviceTime.nowIsoString())
            app.settingsStore.recordContinuousMonitoringStarted(DeviceTime.nowIsoString())
            val initialNext = MonitoringRuntime.nextAt(DeviceTime.nowInstant(), settings.intervalMinutes)
            app.settingsStore.recordRuntimeSchedule(
                settings.intervalMinutes, ScheduleModes.CONTINUOUS, initialNext,
                CheckStates.WAITING, DeviceTime.nowIsoString()
            )
            app.repository.writeLog("info", "work", "continuous monitoring started", "interval=${settings.intervalMinutes}m")
            try {
                while (true) {
                    val latestBeforeDelay = app.settingsStore.settings.first()
                    delay(latestBeforeDelay.intervalMinutes * 60_000L)
                    val latest = app.settingsStore.settings.first()
                    if (!latest.enabled || !latest.continuousMonitoringEnabled || latest.intervalMinutes >= RefreshIntervals.MIN_WORK_MANAGER_MINUTES) break
                    app.settingsStore.recordWorkerStarted(DeviceTime.nowIsoString())
                    val result = app.repository.refreshAllExistingVideos(RefreshTrigger.AUTO)
                    if (result.total == 0) {
                        stopWithResult("stopped: no videos")
                        return@launch
                    }
                    val finishedAt = DeviceTime.nowInstant()
                    app.settingsStore.recordWorkerFinished(
                        finishedAt.toString(),
                        "total=${result.total}, success=${result.success}, failed=${result.failed}",
                        successDelta = result.success.toLong(), failureDelta = result.failed.toLong()
                    )
                    app.settingsStore.recordRuntimeSchedule(
                        latest.intervalMinutes, ScheduleModes.CONTINUOUS,
                        MonitoringRuntime.nextAt(finishedAt, latest.intervalMinutes),
                        CheckStates.WAITING, finishedAt.toString()
                    )
                    val notificationResult = MonitorNotificationManager.maybeNotifyRefreshResult(this@ContinuousMonitoringService, latest, result, finishedAt)
                    app.settingsStore.recordNotificationAttempt(finishedAt.toString(), notificationResult.value)
                    app.repository.writeLog(
                        "info",
                        "work",
                        "continuous monitoring cycle finished",
                        "total=${result.total}, success=${result.success}, failed=${result.failed}, notification=${notificationResult.value}"
                    )
                }
                stopWithResult("settings changed")
            } catch (_: CancellationException) {
                // Normal service shutdown.
            } catch (exc: Exception) {
                app.repository.writeLog("error", "work", "continuous monitoring failed", exc.javaClass.simpleName + ": " + (exc.message ?: "unknown"))
                stopWithResult("failed: ${exc.javaClass.simpleName}")
            }
        }
    }

    override fun onDestroy() {
        loopJob?.cancel()
        scope.cancel()
        super.onDestroy()
    }

    override fun onTimeout(startId: Int, fgsType: Int) {
        stopWithResult("system foreground-service timeout")
    }

    private fun startForegroundNotification(intervalMinutes: Long?) {
        ensureChannel()
        val openIntent = PendingIntent.getActivity(this, 10, Intent(this, MainActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val stopIntent = PendingIntent.getService(this, 11, Intent(this, ContinuousMonitoringService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle("B站数据监控正在后台运行")
            .setContentText(foregroundNotificationText(intervalMinutes))
            .setContentIntent(openIntent)
            .addAction(0, "停止", stopIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()
        ServiceCompat.startForeground(this, NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
    }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java)
        if (manager.getNotificationChannel(CHANNEL_ID) == null) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "后台运行", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "持续监控运行期间显示，停止监控后自动消失"
                }
            )
        }
    }

    private fun channelEnabled(): Boolean {
        ensureChannel()
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.O ||
            getSystemService(NotificationManager::class.java).getNotificationChannel(CHANNEL_ID)?.importance != NotificationManager.IMPORTANCE_NONE
    }

    private fun stopWithResult(
        result: String,
        disablePreference: Boolean = false,
        restorePeriodic: Boolean = true
    ) {
        scope.launch {
            if (disablePreference) app.settingsStore.setContinuousMonitoringEnabled(false)
            if (restorePeriodic) restorePeriodicWork(result)
            else app.settingsStore.recordContinuousMonitoringStopped(DeviceTime.nowIsoString(), result)
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        }
    }

    private suspend fun restorePeriodicWork(result: String) {
        app.settingsStore.recordContinuousMonitoringStopped(DeviceTime.nowIsoString(), result)
        val settings = app.settingsStore.settings.first()
        if (settings.enabled) {
            val shortForeground = settings.intervalMinutes < RefreshIntervals.MIN_WORK_MANAGER_MINUTES
            if (shortForeground) app.autoRefreshScheduler.cancelAndAwait()
            else app.autoRefreshScheduler.scheduleAndAwait(settings.intervalMinutes, settings.wifiOnly)
            val effective = if (shortForeground) settings.intervalMinutes
                else RefreshIntervals.backgroundScheduleMinutes(settings.intervalMinutes)
            val now = DeviceTime.nowInstant()
            app.settingsStore.recordRuntimeSchedule(
                effective, if (shortForeground) ScheduleModes.FOREGROUND else ScheduleModes.WORK_MANAGER,
                MonitoringRuntime.nextAt(now, effective), CheckStates.WAITING, now.toString()
            )
        } else {
            app.settingsStore.recordRuntimeSchedule(
                settings.intervalMinutes, ScheduleModes.OFF, null,
                CheckStates.IDLE, DeviceTime.nowIsoString()
            )
        }
        app.repository.writeLog("info", "work", "continuous monitoring stopped", result)
    }

    companion object {
        const val CHANNEL_ID = "continuous_monitoring"
        const val NOTIFICATION_ONGOING = true
        const val NOTIFICATION_AUTO_CANCEL = false
        const val ACTION_STOP = "com.littletaro.bilibilimonitor.STOP_CONTINUOUS_MONITORING"
        const val ACTION_RECONFIGURE = "com.littletaro.bilibilimonitor.RECONFIGURE_CONTINUOUS_MONITORING"
        const val ACTION_STOP_FOR_RECONFIGURE = "com.littletaro.bilibilimonitor.STOP_CONTINUOUS_FOR_RECONFIGURE"
        private const val NOTIFICATION_ID = 2100

        fun start(context: Context) {
            androidx.core.content.ContextCompat.startForegroundService(context, Intent(context, ContinuousMonitoringService::class.java))
        }

        fun stop(context: Context) {
            context.startService(Intent(context, ContinuousMonitoringService::class.java).setAction(ACTION_STOP))
        }

        fun reconfigure(context: Context) {
            context.startService(Intent(context, ContinuousMonitoringService::class.java).setAction(ACTION_RECONFIGURE))
        }

        fun stopForReconfigure(context: Context) {
            context.startService(Intent(context, ContinuousMonitoringService::class.java).setAction(ACTION_STOP_FOR_RECONFIGURE))
        }

        @JvmStatic
        fun foregroundNotificationText(intervalMinutes: Long?): String =
            intervalMinutes?.let { "当前间隔：$it 分钟；系统可能延迟执行" } ?: "正在启动持续监控"
    }
}
