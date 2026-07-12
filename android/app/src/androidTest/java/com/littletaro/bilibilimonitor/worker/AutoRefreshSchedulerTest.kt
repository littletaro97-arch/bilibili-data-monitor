package com.littletaro.bilibilimonitor.worker

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.work.Configuration
import androidx.work.WorkManager
import androidx.work.testing.SynchronousExecutor
import androidx.work.testing.WorkManagerTestInitHelper
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AutoRefreshSchedulerTest {
    @Test fun updatingIntervalKeepsOneUniquePeriodicRegistration() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        WorkManagerTestInitHelper.initializeTestWorkManager(
            context,
            Configuration.Builder().setExecutor(SynchronousExecutor()).build()
        )
        val scheduler = AutoRefreshScheduler(context)

        scheduler.schedule(15, true)
        scheduler.schedule(30, false)

        val infos = WorkManager.getInstance(context)
            .getWorkInfosForUniqueWork(AutoRefreshScheduler.UNIQUE_WORK_NAME).get()
        assertEquals(1, infos.count { !it.state.isFinished })
    }
}
