package com.littletaro.bilibilimonitor

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.littletaro.bilibilimonitor.ui.MonitorApp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val repository = (application as BilibiliMonitorApplication).repository
        setContent {
            MonitorApp(repository)
        }
    }
}
