package com.littletaro.bilibilimonitor

import android.app.Application
import com.littletaro.bilibilimonitor.data.AppDatabase
import com.littletaro.bilibilimonitor.data.BilibiliApi
import com.littletaro.bilibilimonitor.data.MonitorRepository
import com.littletaro.bilibilimonitor.data.SnapshotExporter
import com.littletaro.bilibilimonitor.settings.AutoRefreshSettingsStore
import com.littletaro.bilibilimonitor.settings.ChartPreferencesStore
import com.littletaro.bilibilimonitor.worker.AutoRefreshScheduler
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import com.littletaro.bilibilimonitor.data.DeviceTime
import com.littletaro.bilibilimonitor.data.DeviceIdentity

class BilibiliMonitorApplication : Application() {
    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        appScope.launch {
            repository.initializeSyncIdentity()
            val current = settingsStore.settings.first()
            if (current.continuousMonitoringRunning) {
                settingsStore.recordContinuousMonitoringStopped(DeviceTime.nowIsoString(), "process restarted; user confirmation required")
            }
        }
    }
    val settingsStore: AutoRefreshSettingsStore by lazy {
        AutoRefreshSettingsStore(this)
    }

    val chartPreferencesStore: ChartPreferencesStore by lazy {
        ChartPreferencesStore(this)
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
        MonitorRepository(database.dao(), BilibiliApi(client), SnapshotExporter(this), DeviceIdentity.get(this))
    }
}
