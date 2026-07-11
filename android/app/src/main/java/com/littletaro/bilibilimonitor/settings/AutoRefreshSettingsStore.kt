package com.littletaro.bilibilimonitor.settings

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.autoRefreshDataStore by preferencesDataStore(name = "auto_refresh_settings")

data class AutoRefreshSettings(
    val enabled: Boolean = false,
    val intervalMinutes: Long = RefreshIntervals.DEFAULT_MINUTES,
    val wifiOnly: Boolean = true,
    val workRegistered: Boolean = false,
    val lastRegisteredAt: String? = null,
    val lastCancelledAt: String? = null,
    val lastAutoRefreshStartedAt: String? = null,
    val lastAutoRefreshFinishedAt: String? = null,
    val lastAutoRefreshResult: String? = null,
    val lastAutoRefreshError: String? = null,
    val autoRefreshSuccessCount: Long = 0,
    val autoRefreshFailureCount: Long = 0,
    val defaultExportTreeUri: String? = null,
    val askExportLocationEveryTime: Boolean = true,
    val defaultExportFormat: String = "csv"
)

object RefreshIntervals {
    const val DEFAULT_MINUTES: Long = 60
    const val MIN_WORK_MANAGER_MINUTES: Long = 15
    val allowedMinutes: List<Long> = listOf(1, 3, 5, 10, 15, 30, 60, 120)

    fun isAllowed(minutes: Long): Boolean = minutes in allowedMinutes

    fun sanitize(minutes: Long): Long =
        if (isAllowed(minutes)) minutes else DEFAULT_MINUTES

    fun backgroundScheduleMinutes(minutes: Long): Long =
        sanitize(minutes).coerceAtLeast(MIN_WORK_MANAGER_MINUTES)
}

class AutoRefreshSettingsStore(private val context: Context) {
    val settings: Flow<AutoRefreshSettings> = context.autoRefreshDataStore.data.map { preferences ->
        AutoRefreshSettings(
            enabled = preferences[Keys.ENABLED] ?: false,
            intervalMinutes = RefreshIntervals.sanitize(
                preferences[Keys.INTERVAL_MINUTES] ?: RefreshIntervals.DEFAULT_MINUTES
            ),
            wifiOnly = preferences[Keys.WIFI_ONLY] ?: true,
            workRegistered = preferences[Keys.WORK_REGISTERED] ?: false,
            lastRegisteredAt = preferences[Keys.LAST_REGISTERED_AT],
            lastCancelledAt = preferences[Keys.LAST_CANCELLED_AT],
            lastAutoRefreshStartedAt = preferences[Keys.LAST_AUTO_REFRESH_STARTED_AT],
            lastAutoRefreshFinishedAt = preferences[Keys.LAST_AUTO_REFRESH_FINISHED_AT],
            lastAutoRefreshResult = preferences[Keys.LAST_AUTO_REFRESH_RESULT],
            lastAutoRefreshError = preferences[Keys.LAST_AUTO_REFRESH_ERROR],
            autoRefreshSuccessCount = preferences[Keys.AUTO_REFRESH_SUCCESS_COUNT] ?: 0,
            autoRefreshFailureCount = preferences[Keys.AUTO_REFRESH_FAILURE_COUNT] ?: 0,
            defaultExportTreeUri = preferences[Keys.DEFAULT_EXPORT_TREE_URI],
            askExportLocationEveryTime = preferences[Keys.ASK_EXPORT_LOCATION_EVERY_TIME] ?: true,
            defaultExportFormat = preferences[Keys.DEFAULT_EXPORT_FORMAT] ?: "csv"
        )
    }

    suspend fun setEnabled(enabled: Boolean) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.ENABLED] = enabled
        }
    }

    suspend fun setIntervalMinutes(minutes: Long) {
        require(RefreshIntervals.isAllowed(minutes)) { "Unsupported interval: $minutes" }
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.INTERVAL_MINUTES] = minutes
        }
    }

    suspend fun setWifiOnly(wifiOnly: Boolean) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.WIFI_ONLY] = wifiOnly
        }
    }

    suspend fun recordRegistered(time: String) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.WORK_REGISTERED] = true
            preferences[Keys.LAST_REGISTERED_AT] = time
            preferences.remove(Keys.LAST_AUTO_REFRESH_ERROR)
        }
    }

    suspend fun recordCancelled(time: String) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.WORK_REGISTERED] = false
            preferences[Keys.LAST_CANCELLED_AT] = time
        }
    }

    suspend fun recordWorkerStarted(time: String) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.LAST_AUTO_REFRESH_STARTED_AT] = time
            preferences[Keys.LAST_AUTO_REFRESH_RESULT] = "running"
            preferences.remove(Keys.LAST_AUTO_REFRESH_ERROR)
        }
    }

    suspend fun recordWorkerFinished(
        time: String,
        result: String,
        error: String? = null,
        successDelta: Long = 0,
        failureDelta: Long = 0
    ) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.LAST_AUTO_REFRESH_FINISHED_AT] = time
            preferences[Keys.LAST_AUTO_REFRESH_RESULT] = result
            preferences[Keys.AUTO_REFRESH_SUCCESS_COUNT] =
                (preferences[Keys.AUTO_REFRESH_SUCCESS_COUNT] ?: 0) + successDelta
            preferences[Keys.AUTO_REFRESH_FAILURE_COUNT] =
                (preferences[Keys.AUTO_REFRESH_FAILURE_COUNT] ?: 0) + failureDelta
            if (error == null) {
                preferences.remove(Keys.LAST_AUTO_REFRESH_ERROR)
            } else {
                preferences[Keys.LAST_AUTO_REFRESH_ERROR] = error
            }
        }
    }

    suspend fun setDefaultExportTreeUri(uri: String?) {
        context.autoRefreshDataStore.edit { preferences ->
            if (uri == null) {
                preferences.remove(Keys.DEFAULT_EXPORT_TREE_URI)
                preferences[Keys.ASK_EXPORT_LOCATION_EVERY_TIME] = true
            } else {
                preferences[Keys.DEFAULT_EXPORT_TREE_URI] = uri
                preferences[Keys.ASK_EXPORT_LOCATION_EVERY_TIME] = false
            }
        }
    }

    suspend fun setAskExportLocationEveryTime(ask: Boolean) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.ASK_EXPORT_LOCATION_EVERY_TIME] = ask
        }
    }

    suspend fun setDefaultExportFormat(format: String) {
        require(format == "csv" || format == "json") { "Unsupported export format: $format" }
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.DEFAULT_EXPORT_FORMAT] = format
        }
    }

    private object Keys {
        val ENABLED = booleanPreferencesKey("enabled")
        val INTERVAL_MINUTES = longPreferencesKey("interval_minutes")
        val WIFI_ONLY = booleanPreferencesKey("wifi_only")
        val WORK_REGISTERED = booleanPreferencesKey("work_registered")
        val LAST_REGISTERED_AT = stringPreferencesKey("last_registered_at")
        val LAST_CANCELLED_AT = stringPreferencesKey("last_cancelled_at")
        val LAST_AUTO_REFRESH_STARTED_AT = stringPreferencesKey("last_auto_refresh_started_at")
        val LAST_AUTO_REFRESH_FINISHED_AT = stringPreferencesKey("last_auto_refresh_finished_at")
        val LAST_AUTO_REFRESH_RESULT = stringPreferencesKey("last_auto_refresh_result")
        val LAST_AUTO_REFRESH_ERROR = stringPreferencesKey("last_auto_refresh_error")
        val AUTO_REFRESH_SUCCESS_COUNT = longPreferencesKey("auto_refresh_success_count")
        val AUTO_REFRESH_FAILURE_COUNT = longPreferencesKey("auto_refresh_failure_count")
        val DEFAULT_EXPORT_TREE_URI = stringPreferencesKey("default_export_tree_uri")
        val ASK_EXPORT_LOCATION_EVERY_TIME = booleanPreferencesKey("ask_export_location_every_time")
        val DEFAULT_EXPORT_FORMAT = stringPreferencesKey("default_export_format")
    }
}
