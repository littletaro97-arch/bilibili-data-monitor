package com.littletaro.bilibilimonitor

import android.app.Application
import com.littletaro.bilibilimonitor.data.AppDatabase
import com.littletaro.bilibilimonitor.data.BilibiliApi
import com.littletaro.bilibilimonitor.data.MonitorRepository
import com.littletaro.bilibilimonitor.data.SnapshotExporter
import com.littletaro.bilibilimonitor.settings.AutoRefreshSettingsStore
import com.littletaro.bilibilimonitor.worker.AutoRefreshScheduler
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

class BilibiliMonitorApplication : Application() {
    val settingsStore: AutoRefreshSettingsStore by lazy {
        AutoRefreshSettingsStore(this)
    }

    val autoRefreshScheduler: AutoRefreshScheduler by lazy {
        AutoRefreshScheduler(this)
    }

    val repository: MonitorRepository by lazy {
        val database = AppDatabase.create(this)
        val client = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .build()
        MonitorRepository(database.dao(), BilibiliApi(client), SnapshotExporter(this))
    }
}
