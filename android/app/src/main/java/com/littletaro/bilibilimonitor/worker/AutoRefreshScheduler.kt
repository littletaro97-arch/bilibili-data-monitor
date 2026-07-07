package com.littletaro.bilibilimonitor.worker

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.littletaro.bilibilimonitor.settings.RefreshIntervals
import java.util.concurrent.TimeUnit

class AutoRefreshScheduler(context: Context) {
    private val appContext = context.applicationContext

    fun schedule(intervalMinutes: Long, wifiOnly: Boolean) {
        val sanitizedInterval = RefreshIntervals.sanitize(intervalMinutes)
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(if (wifiOnly) NetworkType.UNMETERED else NetworkType.CONNECTED)
            .setRequiresBatteryNotLow(true)
            .build()
        val request = PeriodicWorkRequestBuilder<AutoRefreshWorker>(
            sanitizedInterval,
            TimeUnit.MINUTES
        )
            .setConstraints(constraints)
            .addTag(WORK_TAG)
            .build()

        WorkManager.getInstance(appContext).enqueueUniquePeriodicWork(
            UNIQUE_WORK_NAME,
            ExistingPeriodicWorkPolicy.UPDATE,
            request
        )
    }

    fun cancel() {
        WorkManager.getInstance(appContext).cancelUniqueWork(UNIQUE_WORK_NAME)
    }

    companion object {
        const val UNIQUE_WORK_NAME = "bilibili_auto_refresh"
        const val WORK_TAG = "bilibili_auto_refresh"
    }
}
