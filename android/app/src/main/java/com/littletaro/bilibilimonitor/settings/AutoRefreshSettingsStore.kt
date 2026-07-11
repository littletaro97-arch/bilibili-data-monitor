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

data class AutoRefreshSettings @JvmOverloads constructor(
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
    val defaultExportFormat: String = "csv",
    val notificationsEnabled: Boolean = false,
    val notificationPermissionPrompted: Boolean = false,
    val notificationMode: String = NotificationModes.EACH_REFRESH,
    val notificationIntervalMinutes: Long = NotificationIntervals.DEFAULT_MINUTES,
    val lastNotificationSentAt: String? = null,
    val backgroundGuideSeen: Boolean = false,
    val lastNotificationAttemptAt: String? = null,
    val lastNotificationResult: String? = null,
    val continuousMonitoringEnabled: Boolean = false,
    val continuousMonitoringRunning: Boolean = false,
    val continuousMonitoringLastStartedAt: String? = null,
    val continuousMonitoringLastStoppedAt: String? = null,
    val continuousMonitoringLastResult: String? = null
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

object NotificationModes {
    const val EACH_REFRESH = "each_refresh"
    const val SUMMARY = "summary"

    fun sanitize(mode: String): String =
        if (mode == EACH_REFRESH || mode == SUMMARY) mode else EACH_REFRESH
}

object NotificationIntervals {
    const val DEFAULT_MINUTES: Long = 60
    const val STEP_MINUTES: Long = 5
    const val MAX_MINUTES: Long = 24 * 60

    @JvmStatic
    fun lowerBoundMinutes(detectionMinutes: Long): Long =
        ceilToStep(RefreshIntervals.backgroundScheduleMinutes(detectionMinutes).coerceAtLeast(STEP_MINUTES))

    @JvmStatic
    fun sanitize(minutes: Long, detectionMinutes: Long): Long {
        val lowerBound = lowerBoundMinutes(detectionMinutes)
        val bounded = minutes.coerceIn(lowerBound, MAX_MINUTES)
        return ceilToStep(bounded)
    }

    @JvmStatic
    fun options(detectionMinutes: Long): List<Long> {
        val lowerBound = lowerBoundMinutes(detectionMinutes)
        return generateSequence(lowerBound) { current -> current + STEP_MINUTES }
            .takeWhile { it <= MAX_MINUTES }
            .toList()
    }

    private fun ceilToStep(minutes: Long): Long {
        val remainder = minutes % STEP_MINUTES
        return if (remainder == 0L) minutes else minutes + (STEP_MINUTES - remainder)
    }
}

class AutoRefreshSettingsStore(private val context: Context) {
    val settings: Flow<AutoRefreshSettings> = context.autoRefreshDataStore.data.map { preferences ->
        val intervalMinutes = RefreshIntervals.sanitize(
            preferences[Keys.INTERVAL_MINUTES] ?: RefreshIntervals.DEFAULT_MINUTES
        )
        AutoRefreshSettings(
            enabled = preferences[Keys.ENABLED] ?: false,
            intervalMinutes = intervalMinutes,
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
            defaultExportFormat = preferences[Keys.DEFAULT_EXPORT_FORMAT] ?: "csv",
            notificationsEnabled = preferences[Keys.NOTIFICATIONS_ENABLED] ?: false,
            notificationPermissionPrompted = preferences[Keys.NOTIFICATION_PERMISSION_PROMPTED] ?: false,
            notificationMode = NotificationModes.sanitize(
                preferences[Keys.NOTIFICATION_MODE] ?: NotificationModes.EACH_REFRESH
            ),
            notificationIntervalMinutes = NotificationIntervals.sanitize(
                preferences[Keys.NOTIFICATION_INTERVAL_MINUTES] ?: NotificationIntervals.DEFAULT_MINUTES,
                intervalMinutes
            ),
            lastNotificationSentAt = preferences[Keys.LAST_NOTIFICATION_SENT_AT],
            lastNotificationAttemptAt = preferences[Keys.LAST_NOTIFICATION_ATTEMPT_AT],
            lastNotificationResult = preferences[Keys.LAST_NOTIFICATION_RESULT],
            continuousMonitoringEnabled = preferences[Keys.CONTINUOUS_MONITORING_ENABLED] ?: false,
            continuousMonitoringRunning = preferences[Keys.CONTINUOUS_MONITORING_RUNNING] ?: false,
            continuousMonitoringLastStartedAt = preferences[Keys.CONTINUOUS_MONITORING_LAST_STARTED_AT],
            continuousMonitoringLastStoppedAt = preferences[Keys.CONTINUOUS_MONITORING_LAST_STOPPED_AT],
            continuousMonitoringLastResult = preferences[Keys.CONTINUOUS_MONITORING_LAST_RESULT],
            backgroundGuideSeen = preferences[Keys.BACKGROUND_GUIDE_SEEN] ?: false
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
            val currentNotificationInterval =
                preferences[Keys.NOTIFICATION_INTERVAL_MINUTES] ?: NotificationIntervals.DEFAULT_MINUTES
            preferences[Keys.NOTIFICATION_INTERVAL_MINUTES] =
                NotificationIntervals.sanitize(currentNotificationInterval, minutes)
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

    suspend fun setNotificationsEnabled(enabled: Boolean) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.NOTIFICATIONS_ENABLED] = enabled
        }
    }

    suspend fun setNotificationPermissionPrompted(prompted: Boolean) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.NOTIFICATION_PERMISSION_PROMPTED] = prompted
        }
    }

    suspend fun setNotificationMode(mode: String) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.NOTIFICATION_MODE] = NotificationModes.sanitize(mode)
        }
    }

    suspend fun setNotificationIntervalMinutes(minutes: Long, detectionMinutes: Long) {
        val sanitized = NotificationIntervals.sanitize(minutes, detectionMinutes)
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.NOTIFICATION_INTERVAL_MINUTES] = sanitized
        }
    }

    suspend fun recordNotificationSent(time: String) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.LAST_NOTIFICATION_SENT_AT] = time
        }
    }

    suspend fun recordNotificationAttempt(time: String, result: String) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.LAST_NOTIFICATION_ATTEMPT_AT] = time
            preferences[Keys.LAST_NOTIFICATION_RESULT] = result
            if (result == "已发送") preferences[Keys.LAST_NOTIFICATION_SENT_AT] = time
        }
    }

    suspend fun setBackgroundGuideSeen(seen: Boolean) {
        context.autoRefreshDataStore.edit { preferences ->
            preferences[Keys.BACKGROUND_GUIDE_SEEN] = seen
        }
    }

    suspend fun setContinuousMonitoringEnabled(enabled: Boolean) {
        context.autoRefreshDataStore.edit { it[Keys.CONTINUOUS_MONITORING_ENABLED] = enabled }
    }

    suspend fun recordContinuousMonitoringStarted(time: String) {
        context.autoRefreshDataStore.edit {
            it[Keys.CONTINUOUS_MONITORING_RUNNING] = true
            it[Keys.CONTINUOUS_MONITORING_LAST_STARTED_AT] = time
            it[Keys.CONTINUOUS_MONITORING_LAST_RESULT] = "running"
        }
    }

    suspend fun recordContinuousMonitoringStopped(time: String, result: String) {
        context.autoRefreshDataStore.edit {
            it[Keys.CONTINUOUS_MONITORING_RUNNING] = false
            it[Keys.CONTINUOUS_MONITORING_LAST_STOPPED_AT] = time
            it[Keys.CONTINUOUS_MONITORING_LAST_RESULT] = result
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
        val NOTIFICATIONS_ENABLED = booleanPreferencesKey("notifications_enabled")
        val NOTIFICATION_PERMISSION_PROMPTED = booleanPreferencesKey("notification_permission_prompted")
        val NOTIFICATION_MODE = stringPreferencesKey("notification_mode")
        val NOTIFICATION_INTERVAL_MINUTES = longPreferencesKey("notification_interval_minutes")
        val LAST_NOTIFICATION_SENT_AT = stringPreferencesKey("last_notification_sent_at")
        val LAST_NOTIFICATION_ATTEMPT_AT = stringPreferencesKey("last_notification_attempt_at")
        val LAST_NOTIFICATION_RESULT = stringPreferencesKey("last_notification_result")
        val BACKGROUND_GUIDE_SEEN = booleanPreferencesKey("background_guide_seen")
        val CONTINUOUS_MONITORING_ENABLED = booleanPreferencesKey("continuous_monitoring_enabled")
        val CONTINUOUS_MONITORING_RUNNING = booleanPreferencesKey("continuous_monitoring_running")
        val CONTINUOUS_MONITORING_LAST_STARTED_AT = stringPreferencesKey("continuous_monitoring_last_started_at")
        val CONTINUOUS_MONITORING_LAST_STOPPED_AT = stringPreferencesKey("continuous_monitoring_last_stopped_at")
        val CONTINUOUS_MONITORING_LAST_RESULT = stringPreferencesKey("continuous_monitoring_last_result")
    }
}
