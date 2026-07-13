package com.littletaro.bilibilimonitor.settings

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.littletaro.bilibilimonitor.data.TrendMetric
import com.littletaro.bilibilimonitor.data.TrendRange
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map

private val Context.chartPreferencesDataStore by preferencesDataStore(name = "chart_preferences")

enum class ChartDisplayMode { Single, Ratio }

data class ChartPreferences(
    val displayMode: ChartDisplayMode = ChartDisplayMode.Single,
    val singleMetric: TrendMetric = TrendMetric.VIEW,
    val numeratorMetric: TrendMetric = TrendMetric.LIKE,
    val denominatorMetric: TrendMetric = TrendMetric.VIEW,
    val range: TrendRange = TrendRange.TWENTY
) {
    fun sanitized(): ChartPreferences =
        if (numeratorMetric != denominatorMetric) this else copy(
            numeratorMetric = TrendMetric.LIKE,
            denominatorMetric = TrendMetric.VIEW
        )
}

/** Stores compact per-BV presentation state only; it never participates in history exchange. */
class ChartPreferencesStore(private val context: Context) {
    fun preferences(bvId: String): Flow<ChartPreferences> = context.chartPreferencesDataStore.data
        .catch { emit(androidx.datastore.preferences.core.emptyPreferences()) }
        .map { preferences -> ChartPreferencesCodec.decode(preferences[configKey(bvId)]) }
        .distinctUntilChanged()

    suspend fun save(bvId: String, value: ChartPreferences) {
        context.chartPreferencesDataStore.edit { preferences ->
            preferences[configKey(bvId)] = ChartPreferencesCodec.encode(value.sanitized())
        }
    }

    /** Ready for a future video-delete action; the current app has no delete UI. */
    suspend fun clear(bvId: String) {
        context.chartPreferencesDataStore.edit { preferences -> preferences.remove(configKey(bvId)) }
    }

    private fun configKey(bvId: String) = stringPreferencesKey("video.$bvId")
}

internal object ChartPreferencesCodec {
    private const val separator = "|"

    fun encode(value: ChartPreferences): String = value.sanitized().let {
        listOf(it.displayMode.name, it.singleMetric.name, it.numeratorMetric.name, it.denominatorMetric.name, it.range.name)
            .joinToString(separator)
    }

    fun decode(value: String?): ChartPreferences {
        val parts = value?.split(separator) ?: return ChartPreferences()
        if (parts.size != 5) return ChartPreferences()
        return runCatching {
            ChartPreferences(
                displayMode = ChartDisplayMode.valueOf(parts[0]),
                singleMetric = TrendMetric.valueOf(parts[1]),
                numeratorMetric = TrendMetric.valueOf(parts[2]),
                denominatorMetric = TrendMetric.valueOf(parts[3]),
                range = TrendRange.valueOf(parts[4])
            ).sanitized()
        }.getOrElse { ChartPreferences() }
    }
}
