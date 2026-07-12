package com.littletaro.bilibilimonitor.settings

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AutoRefreshSettingsStoreTest {
    @Test fun intervalAndAppliedRuntimeStateAreRestoredFromDataStore() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val store = AutoRefreshSettingsStore(context)
        store.setIntervalMinutes(5)
        store.recordRuntimeSchedule(
            5, ScheduleModes.CONTINUOUS, "2026-07-12T00:05:00Z",
            CheckStates.WAITING, "2026-07-12T00:00:00Z"
        )

        val restored = store.settings.first()

        assertEquals(5L, restored.intervalMinutes)
        assertEquals(5L, restored.effectiveIntervalMinutes)
        assertEquals(ScheduleModes.CONTINUOUS, restored.scheduleMode)
        assertEquals("2026-07-12T00:05:00Z", restored.nextScheduledCheckAt)
    }
}
