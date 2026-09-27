package com.littletaro.bilibilimonitor.worker

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.littletaro.bilibilimonitor.data.AppDatabase
import com.littletaro.bilibilimonitor.data.BilibiliApi
import com.littletaro.bilibilimonitor.data.DeviceTime
import com.littletaro.bilibilimonitor.data.DeviceIdentity
import com.littletaro.bilibilimonitor.data.MonitorRepository
import com.littletaro.bilibilimonitor.data.RefreshTrigger
import com.littletaro.bilibilimonitor.data.SnapshotExporter
import com.littletaro.bilibilimonitor.notifications.MonitorNotificationManager
import com.littletaro.bilibilimonitor.settings.AutoRefreshSettingsStore
import com.littletaro.bilibilimonitor.settings.RefreshIntervals
import com.littletaro.bilibilimonitor.settings.CheckStates
import com.littletaro.bilibilimonitor.settings.MonitoringRuntime
import com.littletaro.bilibilimonitor.settings.ScheduleModes
import kotlinx.coroutines.flow.first
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

class AutoRefreshWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val settingsStore = AutoRefreshSettingsStore(applicationContext)
        val settings = settingsStore.settings.first()
        val database = AppDatabase.create(applicationContext)
        val repository = MonitorRepository(
            database.dao(),
            BilibiliApi(
                OkHttpClient.Builder()
                    .connectTimeout(10, TimeUnit.SECONDS)
                    .readTimeout(10, TimeUnit.SECONDS)
                    .build()
            ),
            SnapshotExporter(applicationContext),
            DeviceIdentity.get(applicationContext)
        )
        repository.initializeSyncIdentity()

        if (!settings.enabled) {
            settingsStore.recordWorkerFinished(
                DeviceTime.nowIsoString(),
                "skipped: settings disabled"
            )
            settingsStore.recordRuntimeSchedule(
                settings.intervalMinutes, ScheduleModes.OFF, null,
                CheckStates.IDLE, DeviceTime.nowIsoString()
            )
            repository.writeLog("info", "work", "auto refresh skipped", "settings disabled")
            return Result.success()
        }

        return try {
            val startedAt = DeviceTime.nowIsoString()
            settingsStore.recordWorkerStarted(startedAt)
            repository.writeLog(
                "info",
                "work",
                "auto refresh worker started",
                "selected=${settings.intervalMinutes}m, effective=${RefreshIntervals.backgroundScheduleMinutes(settings.intervalMinutes)}m"
            )
            val result = repository.refreshAllExistingVideos(RefreshTrigger.AUTO)
            val finishedAt = DeviceTime.nowInstant()
            val now = DeviceTime.nowIsoString()
            val resultText = AutoRefreshWorkerStatus.finished(result)
            settingsStore.recordWorkerFinished(
                now,
                resultText,
                successDelta = result.success.toLong(),
                failureDelta = result.failed.toLong()
            )
            val effective = RefreshIntervals.backgroundScheduleMinutes(settings.intervalMinutes)
            settingsStore.recordRuntimeSchedule(
                effective, ScheduleModes.WORK_MANAGER,
                MonitoringRuntime.nextAt(finishedAt, effective),
                CheckStates.WAITING, finishedAt.toString()
            )
            repository.writeLog(
                "info",
                "work",
                "auto refresh worker finished",
                "$resultText, time=$now"
            )
            val notificationResult = MonitorNotificationManager.maybeNotifyRefreshResult(applicationContext, settings, result, finishedAt)
            settingsStore.recordNotificationAttempt(now, notificationResult.value)
            repository.writeLog(
                if (notificationResult == MonitorNotificationManager.SendResult.SENT) "info" else "warning",
                "notification", "auto refresh notification attempt", notificationResult.value
            )
            Result.success()
        } catch (exc: Exception) {
            val error = AutoRefreshWorkerStatus.failed(exc)
            settingsStore.recordWorkerFinished(
                DeviceTime.nowIsoString(),
                "failed",
                error,
                failureDelta = 1
            )
            repository.writeLog(
                "error",
                "work",
                "auto refresh worker failed",
                error
            )
            Result.success()
        }
    }
}
