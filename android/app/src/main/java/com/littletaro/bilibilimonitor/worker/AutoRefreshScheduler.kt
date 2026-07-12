package com.littletaro.bilibilimonitor.worker

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkInfo
import com.littletaro.bilibilimonitor.settings.AutoRefreshRegistrationClient
import com.littletaro.bilibilimonitor.settings.RefreshIntervals
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

class AutoRefreshScheduler(context: Context) : AutoRefreshRegistrationClient {
    private val appContext = context.applicationContext

    override fun schedule(intervalMinutes: Long, wifiOnly: Boolean) {
        enqueue(intervalMinutes, wifiOnly)
    }

    suspend fun scheduleAndAwait(intervalMinutes: Long, wifiOnly: Boolean) {
        withContext(Dispatchers.IO) { enqueue(intervalMinutes, wifiOnly).result.get() }
    }

    private fun enqueue(intervalMinutes: Long, wifiOnly: Boolean): androidx.work.Operation {
        val sanitizedInterval = RefreshIntervals.backgroundScheduleMinutes(intervalMinutes)
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

        return WorkManager.getInstance(appContext).enqueueUniquePeriodicWork(
            UNIQUE_WORK_NAME,
            ExistingPeriodicWorkPolicy.UPDATE,
            request
        )
    }

    override fun cancel() {
        WorkManager.getInstance(appContext).cancelUniqueWork(UNIQUE_WORK_NAME)
    }

    suspend fun cancelAndAwait() {
        withContext(Dispatchers.IO) {
            WorkManager.getInstance(appContext).cancelUniqueWork(UNIQUE_WORK_NAME).result.get()
        }
    }

    fun workInfoFlow(): Flow<WorkInfo?> = flow {
        while (true) {
            val infos = withContext(Dispatchers.IO) {
                WorkManager.getInstance(appContext).getWorkInfosForUniqueWork(UNIQUE_WORK_NAME).get()
            }
            emit(infos.maxByOrNull { it.id.toString() })
            delay(10_000)
        }
    }

    companion object {
        const val UNIQUE_WORK_NAME = "bilibili_auto_refresh"
        const val WORK_TAG = "bilibili_auto_refresh"
    }
}
