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
    val lastAutoRefreshAt: String? = null
)

object RefreshIntervals {
    const val DEFAULT_MINUTES: Long = 60
    val allowedMinutes: List<Long> = listOf(15, 30, 60, 180, 360)

    fun isAllowed(minutes: Long): Boolean = minutes in allowedMinutes

    fun sanitize(minutes: Long): Long =
        if (isAllowed(minutes)) minutes else DEFAULT_MINUTES
}

class AutoRefreshSettingsStore(private val context: Context) {
    val settings: Flow<AutoRefreshSettings> = context.autoRefreshDataStore.data.map { preferences ->
        AutoRefreshSettings(
            enabled = preferences[Keys.ENABLED] ?: false,
            intervalMinutes = RefreshIntervals.sanitize(
                preferences[Keys.INTERVAL_MINUTES] ?: RefreshIntervals.DEFAULT_MINUTES
            ),
            wifiOnly = preferences[Keys.WIFI_ONLY] ?: true,
            lastAutoRefreshAt = preferences[Keys.LAST_AUTO_REFRESH_AT]
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

    suspend fun recordLastAutoRefreshAt(time: String) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.LAST_AUTO_REFRESH_AT] = time
        }
    }

    private object Keys {
        val ENABLED = booleanPreferencesKey("enabled")
        val INTERVAL_MINUTES = longPreferencesKey("interval_minutes")
        val WIFI_ONLY = booleanPreferencesKey("wifi_only")
        val LAST_AUTO_REFRESH_AT = stringPreferencesKey("last_auto_refresh_at")
    }
}
