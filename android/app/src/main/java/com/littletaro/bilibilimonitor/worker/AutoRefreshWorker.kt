package com.littletaro.bilibilimonitor.worker

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.littletaro.bilibilimonitor.data.AppDatabase
import com.littletaro.bilibilimonitor.data.BilibiliApi
import com.littletaro.bilibilimonitor.data.MonitorRepository
import com.littletaro.bilibilimonitor.data.RefreshTrigger
import com.littletaro.bilibilimonitor.data.SnapshotExporter
import com.littletaro.bilibilimonitor.settings.AutoRefreshSettingsStore
import kotlinx.coroutines.flow.first
import okhttp3.OkHttpClient
import java.time.Instant
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
            SnapshotExporter(applicationContext)
        )

        if (!settings.enabled) {
            repository.writeLog("info", "work", "auto refresh skipped", "settings disabled")
            return Result.success()
        }

        return try {
            repository.writeLog("info", "work", "auto refresh worker started", "interval=${settings.intervalMinutes}m")
            val result = repository.refreshAllExistingVideos(RefreshTrigger.AUTO)
            val now = Instant.now().toString()
            settingsStore.recordLastAutoRefreshAt(now)
            repository.writeLog(
                "info",
                "work",
                "auto refresh worker finished",
                "total=${result.total}, success=${result.success}, failed=${result.failed}, time=$now"
            )
            Result.success()
        } catch (exc: Exception) {
            repository.writeLog(
                "error",
                "work",
                "auto refresh worker failed",
                "${exc.javaClass.simpleName}: ${exc.message}; no immediate retry"
            )
            Result.success()
        }
    }
}
