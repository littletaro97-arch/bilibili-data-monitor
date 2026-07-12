package com.littletaro.bilibilimonitor.ui

import android.Manifest
import android.content.Intent
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.core.content.FileProvider
import androidx.core.content.ContextCompat
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.littletaro.bilibilimonitor.data.AppLogEntity
import com.littletaro.bilibilimonitor.data.DeviceTime
import com.littletaro.bilibilimonitor.data.ExportPayload
import com.littletaro.bilibilimonitor.data.ExportResult
import com.littletaro.bilibilimonitor.data.HistoryExchangeCodec
import com.littletaro.bilibilimonitor.data.HistoryImportPreview
import com.littletaro.bilibilimonitor.data.HistoryImportReport
import com.littletaro.bilibilimonitor.data.MonitorRepository
import com.littletaro.bilibilimonitor.data.RefreshAllResult
import com.littletaro.bilibilimonitor.data.SnapshotSources
import com.littletaro.bilibilimonitor.data.RefreshTrigger
import com.littletaro.bilibilimonitor.data.TrendCalculator
import com.littletaro.bilibilimonitor.data.TrendMetric
import com.littletaro.bilibilimonitor.data.TrendPoint
import com.littletaro.bilibilimonitor.data.VideoEntity
import com.littletaro.bilibilimonitor.data.VideoSnapshotEntity
import com.littletaro.bilibilimonitor.notifications.MonitorNotificationManager
import com.littletaro.bilibilimonitor.navigation.AndroidVideoIntentStarter
import com.littletaro.bilibilimonitor.navigation.VideoLinkOpener
import com.littletaro.bilibilimonitor.settings.AutoRefreshSettings
import com.littletaro.bilibilimonitor.settings.AutoRefreshSettingsStore
import com.littletaro.bilibilimonitor.settings.AutoRefreshRegistrationController
import com.littletaro.bilibilimonitor.settings.BackgroundRunStatus
import com.littletaro.bilibilimonitor.settings.NotificationIntervals
import com.littletaro.bilibilimonitor.settings.NotificationModes
import com.littletaro.bilibilimonitor.settings.RefreshIntervals
import com.littletaro.bilibilimonitor.settings.CheckStates
import com.littletaro.bilibilimonitor.settings.MonitoringRuntime
import com.littletaro.bilibilimonitor.settings.ScheduleModes
import com.littletaro.bilibilimonitor.worker.AutoRefreshScheduler
import com.littletaro.bilibilimonitor.worker.ContinuousMonitoringService
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import java.io.File
import java.time.Instant
import kotlin.math.abs

private enum class Page {
    Home,
    Detail,
    History,
    Settings,
    Advanced
}

@Composable
fun MonitorApp(
    repository: MonitorRepository,
    settingsStore: AutoRefreshSettingsStore,
    autoRefreshScheduler: AutoRefreshScheduler
) {
    MaterialTheme {
        Surface(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
        ) {
            val context = LocalContext.current
            val scope = rememberCoroutineScope()
            val videos by repository.videos.collectAsStateWithLifecycle(initialValue = emptyList())
            val appSettings by settingsStore.settings.collectAsStateWithLifecycle(initialValue = AutoRefreshSettings())
            val autoWorkInfo by autoRefreshScheduler.workInfoFlow().collectAsStateWithLifecycle(initialValue = null)
            var page by rememberSaveable { mutableStateOf(Page.Home) }
            var selectedBvId by rememberSaveable { mutableStateOf<String?>(null) }
            val hasValidSelection = selectedBvId != null && videos.any { it.bvId == selectedBvId }
            val notificationPermissionLauncher = rememberLauncherForActivityResult(
                ActivityResultContracts.RequestPermission()
            ) { granted ->
                scope.launch {
                    settingsStore.setNotificationPermissionPrompted(true)
                    if (!granted) settingsStore.setNotificationsEnabled(false)
                }
            }
            val shouldShowNotificationIntro =
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                    !MonitorNotificationManager.permissionGranted(context) &&
                    !appSettings.notificationPermissionPrompted
            val shouldShowBackgroundGuide = !appSettings.backgroundGuideSeen && !shouldShowNotificationIntro

            BackHandler(enabled = shouldShowNotificationIntro || shouldShowBackgroundGuide || page != Page.Home) {
                when (NavigationBackPolicy.action(shouldShowNotificationIntro || shouldShowBackgroundGuide, page == Page.Home)) {
                    BackAction.CLOSE_OVERLAY -> if (shouldShowNotificationIntro) {
                        scope.launch { settingsStore.setNotificationPermissionPrompted(true) }
                    } else {
                        scope.launch { settingsStore.setBackgroundGuideSeen(true) }
                    }
                    BackAction.GO_HOME -> page = Page.Home
                    BackAction.SYSTEM_DEFAULT -> Unit
                }
            }

            LaunchedEffect(videos, selectedBvId) {
                if (selectedBvId != null && TopNavigationModel.resolveSelection(selectedBvId, videos.map { it.bvId }) == null) {
                    selectedBvId = null
                    if (page == Page.Detail || page == Page.History) {
                        page = Page.Home
                    }
                }
            }

            LaunchedEffect(
                autoWorkInfo?.id,
                autoWorkInfo?.state,
                autoWorkInfo?.nextScheduleTimeMillis,
                appSettings.enabled,
                appSettings.intervalMinutes
            ) {
                if (appSettings.enabled && appSettings.intervalMinutes >= RefreshIntervals.MIN_WORK_MANAGER_MINUTES) {
                    val effective = RefreshIntervals.backgroundScheduleMinutes(appSettings.intervalMinutes)
                    val nextMillis = autoWorkInfo?.nextScheduleTimeMillis?.takeIf { it > 0L }
                    val state = when (autoWorkInfo?.state?.name) {
                        "RUNNING" -> CheckStates.RUNNING
                        "FAILED", "CANCELLED" -> CheckStates.FAILED
                        else -> CheckStates.WAITING
                    }
                    settingsStore.recordRuntimeSchedule(
                        effective, ScheduleModes.WORK_MANAGER,
                        nextMillis?.let { Instant.ofEpochMilli(it).toString() }
                            ?: MonitoringRuntime.nextAt(DeviceTime.nowInstant(), effective),
                        state, DeviceTime.nowIsoString()
                    )
                }
            }

            LaunchedEffect(appSettings.enabled, appSettings.intervalMinutes, appSettings.continuousMonitoringEnabled) {
                if (!appSettings.enabled || appSettings.continuousMonitoringEnabled || appSettings.intervalMinutes >= RefreshIntervals.MIN_WORK_MANAGER_MINUTES) return@LaunchedEffect
                repository.writeLog("info", "work", "foreground refresh loop started", "interval=${appSettings.intervalMinutes}m")
                settingsStore.recordRuntimeSchedule(
                    appSettings.intervalMinutes, ScheduleModes.FOREGROUND,
                    MonitoringRuntime.nextAt(DeviceTime.nowInstant(), appSettings.intervalMinutes),
                    CheckStates.WAITING, DeviceTime.nowIsoString()
                )
                while (true) {
                    delay(appSettings.intervalMinutes * 60_000L)
                    settingsStore.recordWorkerStarted(DeviceTime.nowIsoString())
                    val result = repository.refreshAllExistingVideos(RefreshTrigger.AUTO)
                    val finishedAt = DeviceTime.nowInstant()
                    settingsStore.recordWorkerFinished(
                        finishedAt.toString(),
                        "total=${result.total}, success=${result.success}, failed=${result.failed}",
                        successDelta = result.success.toLong(), failureDelta = result.failed.toLong()
                    )
                    settingsStore.recordRuntimeSchedule(
                        appSettings.intervalMinutes, ScheduleModes.FOREGROUND,
                        MonitoringRuntime.nextAt(finishedAt, appSettings.intervalMinutes),
                        CheckStates.WAITING, finishedAt.toString()
                    )
                    val outcome = MonitorNotificationManager.maybeNotifyRefreshResult(
                        context, appSettings, result, finishedAt
                    )
                    settingsStore.recordNotificationAttempt(DeviceTime.nowIsoString(), outcome.value)
                    repository.writeLog("info", "work", "foreground auto refresh finished", "total=${result.total}, notification=${outcome.value}")
                }
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 16.dp)
                    .padding(top = 12.dp)
            ) {
                Text("B站数据监控 Android MVP", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                val backgroundRestricted = appSettings.enabled && (
                    (!appSettings.workRegistered && !appSettings.continuousMonitoringRunning) ||
                        appSettings.autoRefreshFailureCount >= 3 ||
                        (appSettings.continuousMonitoringEnabled &&
                            (!appSettings.continuousMonitoringRunning || !MonitorNotificationManager.permissionGranted(context)))
                    )
                NavRow(page, hasValidSelection, backgroundRestricted) { target ->
                    if ((target == Page.Detail || target == Page.History) && !hasValidSelection) {
                        page = Page.Home
                    } else {
                        page = target
                    }
                }
                Spacer(Modifier.height(12.dp))
                Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
                    when (page) {
                        Page.Home -> HomePage(repository, settingsStore) {
                            selectedBvId = it
                            page = Page.Detail
                        }
                        Page.Detail -> if (hasValidSelection) DetailPage(repository, settingsStore, selectedBvId!!) { page = Page.Settings } else EmptySelection()
                        Page.History -> if (hasValidSelection) HistoryPage(repository, selectedBvId!!) else EmptySelection()
                        Page.Settings -> SettingsPage(repository, settingsStore, autoRefreshScheduler)
                        Page.Advanced -> AdvancedPage(repository, settingsStore, selectedBvId.takeIf { hasValidSelection })
                    }
                }
            }
            if (shouldShowNotificationIntro) {
                NotificationPermissionIntroDialog(
                    onRequest = {
                        scope.launch { settingsStore.setNotificationPermissionPrompted(true) }
                        notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    },
                    onSkip = {
                        scope.launch { settingsStore.setNotificationPermissionPrompted(true) }
                    }
                )
            }
            if (shouldShowBackgroundGuide) {
                BackgroundGuideDialog(
                    onOpenSettings = {
                        scope.launch { settingsStore.setBackgroundGuideSeen(true) }
                        page = Page.Settings
                    },
                    onSkip = {
                        scope.launch { settingsStore.setBackgroundGuideSeen(true) }
                    }
                )
            }
        }
    }
}

@Composable
private fun NotificationPermissionIntroDialog(
    onRequest: () -> Unit,
    onSkip: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onSkip,
        title = { Text("通知提醒") },
        text = {
            Text("通知用于显示监控检测结果，可以随时在设置中关闭；不授权也不影响核心监控和数据查看。")
        },
        confirmButton = {
            Button(onClick = onRequest) { Text("开启通知") }
        },
        dismissButton = {
            TextButton(onClick = onSkip) { Text("暂不开启") }
        }
    )
}

@Composable
private fun BackgroundGuideDialog(
    onOpenSettings: () -> Unit,
    onSkip: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onSkip,
        title = { Text("后台运行") },
        text = {
            Text("后台监控由 Android 系统调度，可能受到电池优化和厂商后台策略影响。相关配置均为可选，跳过后仍可正常使用。")
        },
        confirmButton = {
            Button(onClick = onOpenSettings) { Text("查看设置") }
        },
        dismissButton = {
            TextButton(onClick = onSkip) { Text("稍后") }
        }
    )
}

@Composable
private fun NavRow(current: Page, hasSelection: Boolean, backgroundRestricted: Boolean, onSelect: (Page) -> Unit) {
    val pageByLabel = mapOf(
        "首页" to Page.Home,
        "详情" to Page.Detail,
        "历史" to Page.History,
        "设置" to Page.Settings,
        "高级" to Page.Advanced
    )
    val items = TopNavigationModel.labels(hasSelection).mapNotNull { pageByLabel[it] }
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        items(items) { item ->
            val selected = item == current
            if (selected) {
                Button(onClick = { onSelect(item) }) { Text(pageLabel(item, backgroundRestricted)) }
            } else {
                TextButton(onClick = { onSelect(item) }) { Text(pageLabel(item, backgroundRestricted)) }
            }
        }
    }
}

@Composable
private fun HomePage(
    repository: MonitorRepository,
    settingsStore: AutoRefreshSettingsStore,
    onOpenVideo: (String) -> Unit
) {
    val context = LocalContext.current
    val videos by repository.videos.collectAsStateWithLifecycle(initialValue = emptyList())
    val scope = rememberCoroutineScope()
    var input by remember { mutableStateOf("") }
    var status by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }

    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = pageContentPadding()
    ) {
        item {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                label = { Text("BV 号或 Bilibili 视频链接") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(
                    onClick = {
                        scope.launch {
                            loading = true
                            try {
                                status = runCatching {
                                    val bvId = repository.addVideo(input)
                                    onOpenVideo(bvId)
                                    "已添加 $bvId"
                                }.getOrElse { it.message ?: "解析失败" }
                            } finally {
                                loading = false
                            }
                        }
                    },
                    enabled = input.isNotBlank() && !loading,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("解析 / 添加")
                }
                Button(
                    onClick = {
                        scope.launch {
                            loading = true
                            try {
                                status = runCatching {
                                    val bvId = repository.addVideo(input)
                                    repository.refresh(bvId, RefreshTrigger.MANUAL)
                                    notifyManualRefresh(repository, settingsStore, context)
                                    onOpenVideo(bvId)
                                    "刷新完成 $bvId"
                                }.getOrElse { it.message ?: "刷新失败" }
                            } finally {
                                loading = false
                            }
                        }
                    },
                    enabled = input.isNotBlank() && !loading,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("刷新数据")
                }
                if (loading) CircularProgressIndicator()
                status?.let { Text(it) }
            }
        }
        item { Text("最近视频", style = MaterialTheme.typography.titleMedium) }
        if (videos.isEmpty()) {
            item { Text("暂无视频，请先输入 BV 号或视频链接") }
        } else {
            items(videos, key = { it.bvId }) { video ->
                VideoCard(repository, video, onOpenVideo)
            }
        }
    }
}

@Composable
private fun VideoCard(repository: MonitorRepository, video: VideoEntity, onOpenVideo: (String) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var openError by remember { mutableStateOf<String?>(null) }
    var openingExternal by remember { mutableStateOf(false) }
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            ExpandableText(
                text = video.title ?: "未刷新标题",
                collapsedMaxLines = 2,
                fontWeight = FontWeight.Bold
            )
            Text("BV: ${video.bvId}")
            Text("UP: ${video.authorName ?: "未知"}")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { onOpenVideo(video.bvId) }) { Text("详情") }
                Button(
                    enabled = !openingExternal,
                    onClick = {
                        openingExternal = true
                        val result = runCatching {
                            VideoLinkOpener(AndroidVideoIntentStarter(context)).open(video.bvId)
                        }
                        openError = result.fold(
                            onSuccess = { it.errorMessage },
                            onFailure = { if (it is IllegalArgumentException) "无效 BV 号" else "未找到可以打开该视频链接的应用" }
                        )
                        scope.launch {
                            val detail = result.getOrNull()?.logDetail()
                                ?: "bvId=${video.bvId}, exception=${result.exceptionOrNull()?.javaClass?.simpleName}"
                            repository.writeLog(
                                if (result.getOrNull()?.succeeded == true) "info" else "warning",
                                "navigation",
                                "external video open",
                                detail
                            )
                            delay(600)
                            openingExternal = false
                        }
                    }
                ) { Text("打开") }
            }
            openError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }
}

@Composable
private fun DetailPage(
    repository: MonitorRepository,
    settingsStore: AutoRefreshSettingsStore,
    bvId: String,
    onOpenSettings: () -> Unit
) {
    val context = LocalContext.current
    val videos by repository.videos.collectAsStateWithLifecycle(initialValue = emptyList())
    val latest by repository.latestSnapshot(bvId).collectAsStateWithLifecycle(initialValue = null)
    val settings by settingsStore.settings.collectAsStateWithLifecycle(initialValue = AutoRefreshSettings())
    val video = videos.firstOrNull { it.bvId == bvId }
    val scope = rememberCoroutineScope()
    var message by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = pageContentPadding()
    ) {
        item {
            Card {
                Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("视频信息", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    ExpandableText("标题：${video?.title ?: "未刷新"}", collapsedMaxLines = 2)
                    Text("UP：${video?.authorName ?: "未知"} · BV：$bvId")
                    Text("aid：${video?.aid ?: "-"} · 发布时间：${video?.pubdate ?: "-"}", style = MaterialTheme.typography.bodySmall)
                    Text("状态：${latest?.fetchStatus ?: "尚未检查"}", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        item { CheckTimerCard(settings, onOpenSettings) }
        item {
            Button(
                onClick = {
                    scope.launch {
                        loading = true
                        try {
                            repository.refresh(bvId, RefreshTrigger.MANUAL)
                            notifyManualRefresh(repository, settingsStore, context)
                            message = "刷新请求已完成"
                        } finally {
                            loading = false
                        }
                    }
                },
                enabled = !loading,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("手动刷新")
            }
        }
        if (loading) {
            item { CircularProgressIndicator() }
        }
        message?.let { text ->
            item { Text(text) }
        }
        item {
            SnapshotBlock(latest)
        }
    }
}

@Composable
private fun CheckTimerCard(settings: AutoRefreshSettings, onOpenSettings: () -> Unit) {
    var now by remember { mutableStateOf(DeviceTime.nowInstant()) }
    LaunchedEffect(settings.nextScheduledCheckAt, settings.checkState, settings.enabled) {
        while (true) {
            now = DeviceTime.nowInstant()
            delay(1_000L)
        }
    }
    val countdown = remember(settings, now) { MonitoringRuntime.countdown(settings, now) }
    Card {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("检查计时", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text("状态：${MonitoringRuntime.modeLabel(settings.scheduleMode)}")
            Text("有效间隔：${minutesLabel(settings.effectiveIntervalMinutes)}")
            Text(countdown.headline, fontWeight = FontWeight.Bold)
            countdown.progress?.let { LinearProgressIndicator(progress = { it }, modifier = Modifier.fillMaxWidth()) }
            Text(countdown.nextLabel, style = MaterialTheme.typography.bodySmall)
            if (!settings.enabled) TextButton(onClick = onOpenSettings) { Text("前往设置") }
            settings.lastAutoRefreshError?.takeIf { settings.checkState == CheckStates.FAILED }?.let {
                ExpandableText("错误：$it", collapsedMaxLines = 2)
            }
        }
    }
}

@Composable
private fun SnapshotBlock(snapshot: VideoSnapshotEntity?) {
    if (snapshot == null) {
        Text("暂无快照")
        return
    }
    Card {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("最近快照", fontWeight = FontWeight.Bold)
            Text("采集时间：${DeviceTime.formatForDisplay(snapshot.collectedAt)}")
            Text("状态：${snapshot.fetchStatus}")
            snapshot.errorMessage?.let {
                ExpandableText(text = "错误：$it", collapsedMaxLines = 2)
            } ?: Text("错误：-")
            Text("播放：${snapshot.viewCount ?: "-"}")
            Text("弹幕：${snapshot.danmakuCount ?: "-"}")
            Text("评论：${snapshot.replyCount ?: "-"}")
            Text("收藏：${snapshot.favoriteCount ?: "-"}")
            Text("投币：${snapshot.coinCount ?: "-"}")
            Text("分享：${snapshot.shareCount ?: "-"}")
            Text("点赞：${snapshot.likeCount ?: "-"}")
        }
    }
}

@Composable
private fun HistoryPage(repository: MonitorRepository, bvId: String) {
    val snapshots by repository.snapshots(bvId).collectAsStateWithLifecycle(initialValue = emptyList())
    var metric by remember { mutableStateOf(TrendMetric.VIEW) }
    var limit by remember { mutableStateOf(20) }
    val trendPoints = remember(snapshots, metric, limit) {
        TrendCalculator.points(snapshots, metric, limit)
    }

    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = pageContentPadding()
    ) {
        item { Text("趋势和历史快照", style = MaterialTheme.typography.titleMedium) }
        if (snapshots.isEmpty()) {
            item { Text("暂无历史快照，请先手动刷新") }
        } else {
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
                    items(TrendMetric.entries) { item ->
                        if (metric == item) {
                            Button(onClick = { metric = item }) { Text(item.label) }
                        } else {
                            TextButton(onClick = { metric = item }) { Text(item.label) }
                        }
                    }
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("最近")
                    if (limit == 20) {
                        Button(onClick = { limit = 20 }) { Text("20") }
                    } else {
                        TextButton(onClick = { limit = 20 }) { Text("20") }
                    }
                    if (limit == 50) {
                        Button(onClick = { limit = 50 }) { Text("50") }
                    } else {
                        TextButton(onClick = { limit = 50 }) { Text("50") }
                    }
                    Text("条")
                }
            }
            item { TrendChart(trendPoints, metric) }
            items(snapshots, key = { it.id }) { snapshot ->
                var expanded by rememberSaveable(HistoryExpansionPolicy.stateKey(snapshot.id)) {
                    mutableStateOf(HistoryExpansionPolicy.defaultExpanded())
                }
                Card(modifier = Modifier.fillMaxWidth().animateContentSize()) {
                    Column(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 6.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(DeviceTime.formatForDisplay(snapshot.collectedAt), fontWeight = FontWeight.Bold)
                            Text(snapshotSourceLabel(snapshot.captureSource))
                        }
                        Text("播放 ${snapshot.viewCount ?: "-"} · 点赞 ${snapshot.likeCount ?: "-"} · 评论 ${snapshot.replyCount ?: "-"} · 投币 ${snapshot.coinCount ?: "-"} · 收藏 ${snapshot.favoriteCount ?: "-"}")
                        AnimatedVisibility(expanded) {
                            Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                Text("状态：${snapshot.fetchStatus}")
                                Text("弹幕：${snapshot.danmakuCount ?: "-"} · 分享：${snapshot.shareCount ?: "-"}")
                                Text("来源链接：${snapshot.sourceUrl ?: "-"}", style = MaterialTheme.typography.bodySmall)
                                snapshot.errorMessage?.let { ExpandableText("错误：$it", collapsedMaxLines = 2) }
                                    ?: Text("错误：-", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                        TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "收起" else "展开") }
                    }
                }
            }
        }
    }
}

@Composable
private fun TrendChart(points: List<TrendPoint>, metric: TrendMetric) {
    val validPoints = points.filter { it.value != null }
    val lineColor = MaterialTheme.colorScheme.primary
    val axisColor = MaterialTheme.colorScheme.outline
    val pointColor = MaterialTheme.colorScheme.tertiary
    Card {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("${metric.label}趋势", fontWeight = FontWeight.Bold)
            if (validPoints.isEmpty()) {
                Text("暂无可绘制数据")
                return@Column
            }
            Text("数据点：${validPoints.size} · 最近：${DeviceTime.formatForDisplay(validPoints.last().collectedAt)}")
            Canvas(modifier = Modifier.fillMaxWidth().height(200.dp)) {
                val minValue = validPoints.minOf { it.value ?: 0L }
                val maxValue = validPoints.maxOf { it.value ?: 0L }
                val valueRange = (maxValue - minValue).coerceAtLeast(1L).toFloat()
                val left = 8f
                val right = size.width - 8f
                val top = 8f
                val bottom = size.height - 8f
                drawLine(axisColor, Offset(left, bottom), Offset(right, bottom), strokeWidth = 2f)
                val offsets = validPoints.mapIndexed { index, point ->
                    val x = if (validPoints.size == 1) {
                        (left + right) / 2f
                    } else {
                        left + (right - left) * index / (validPoints.size - 1)
                    }
                    val normalized = ((point.value ?: minValue) - minValue).toFloat() / valueRange
                    val y = bottom - normalized * (bottom - top)
                    Offset(x, y)
                }
                offsets.zipWithNext().forEach { (start, end) ->
                    drawLine(lineColor, start, end, strokeWidth = 4f, cap = StrokeCap.Round)
                }
                offsets.forEachIndexed { index, offset ->
                    val source = validPoints[index].captureSource
                    if (source == SnapshotSources.MANUAL) drawCircle(pointColor, radius = 7f, center = offset)
                    else drawCircle(pointColor, radius = 4f, center = offset)
                }
            }
            Text("最小 ${minValueText(validPoints)} / 最大 ${maxValueText(validPoints)}")
        }
    }
}

private fun snapshotSourceLabel(source: String): String = when (source) {
    SnapshotSources.MANUAL -> "手动采集"
    SnapshotSources.AUTO -> "自动采集"
    else -> "历史数据"
}

@Composable
private fun TrendPointCard(point: TrendPoint, metric: TrendMetric) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(DeviceTime.formatForDisplay(point.collectedAt), fontWeight = FontWeight.Bold)
            Text("${metric.label}：${point.value ?: "-"} / 增量：${point.delta?.toString() ?: "-"}")
        }
    }
}

@Composable
private fun AdvancedPage(
    repository: MonitorRepository,
    settingsStore: AutoRefreshSettingsStore,
    selectedBvId: String?
) {
    val logs by repository.logs.collectAsStateWithLifecycle(initialValue = emptyList())
    val settings by settingsStore.settings.collectAsStateWithLifecycle(initialValue = AutoRefreshSettings())
    var filter by rememberSaveable { mutableStateOf("全部") }
    val filteredLogs = remember(logs, filter) {
        logs.filter { log ->
            when (filter) {
                "info", "warning", "error" -> log.level == filter
                "手动刷新" -> log.message.contains("manual") || log.detail.orEmpty().contains("manual")
                "自动刷新" -> log.message.contains("auto") || log.detail.orEmpty().contains("auto")
                "导出" -> log.tag == "export"
                else -> true
            }
        }
    }
    val pageState = AdvancedPageModel.from(selectedBvId)

    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = pageContentPadding()
    ) {
        item {
            Text("高级", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        }
        item {
            if (pageState.showEmptyExportMessage) {
                Card {
                    Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("导出", fontWeight = FontWeight.Bold)
                        Text("选择视频后可导出 JSON / CSV。")
                    }
                }
            } else if (pageState.showExportPanel && selectedBvId != null) {
                ExportPanel(repository, settingsStore, selectedBvId)
            }
        }
        item {
            ExpandableSection("技术诊断", initiallyExpanded = false, stateKey = "advanced_diagnostics") {
                Text("应用版本：0.11.2")
                Text("数据库版本：3")
                Text("交换格式版本：1")
                AutoRefreshStatusBlock(settings, null, null)
            }
        }
        item {
            Text("日志", style = MaterialTheme.typography.titleMedium)
        }
        item {
            LogFilterRow(filter) { filter = it }
        }
        if (filteredLogs.isEmpty()) {
            item { Text("暂无日志") }
        } else {
            items(filteredLogs, key = { it.id }) { log ->
                LogCard(log)
            }
        }
    }
}

@Composable
private fun ExportPanel(
    repository: MonitorRepository,
    settingsStore: AutoRefreshSettingsStore,
    bvId: String
) {
    val context = LocalContext.current
    val settings by settingsStore.settings.collectAsStateWithLifecycle(initialValue = AutoRefreshSettings())
    val scope = rememberCoroutineScope()
    var output by remember { mutableStateOf("尚未导出") }
    var lastExport by remember { mutableStateOf<ExportResult?>(null) }
    var pendingPayload by remember { mutableStateOf<ExportPayload?>(null) }
    var askDefaultAfterSave by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    fun handleCreatedDocument(uri: Uri?) {
        val payload = pendingPayload
        pendingPayload = null
        if (uri == null || payload == null) {
            output = "已取消保存"
            return
        }
        scope.launch {
            output = writePayloadToUri(context, uri, payload)
            askDefaultAfterSave = settings.defaultExportTreeUri == null
            repository.writeLog("info", "export", "SAF 导出成功", "${payload.fileName}, ${payload.sizeBytes} bytes")
        }
    }
    val createJsonDocumentLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/json")
    ) { uri -> handleCreatedDocument(uri) }
    val createCsvDocumentLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("text/csv")
    ) { uri -> handleCreatedDocument(uri) }
    fun launchCreateDocument(payload: ExportPayload) {
        pendingPayload = payload
        if (payload.mimeType == "application/json") {
            createJsonDocumentLauncher.launch(payload.fileName)
        } else {
            createCsvDocumentLauncher.launch(payload.fileName)
        }
    }
    val openTreeLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocumentTree()
    ) { uri ->
        if (uri == null) {
            output = "未选择默认导出目录"
            return@rememberLauncherForActivityResult
        }
        scope.launch {
            try {
                context.contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                )
                settingsStore.setDefaultExportTreeUri(uri.toString())
                settingsStore.setAskExportLocationEveryTime(false)
                askDefaultAfterSave = false
                output = "已设置默认导出目录"
            } catch (exc: Exception) {
                output = "默认目录授权失败：${exc.message ?: exc.javaClass.simpleName}"
            }
        }
    }

    Card {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("导出 $bvId")
        Column(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            Button(
                onClick = {
                    scope.launch {
                        loading = true
                        try {
                            val payload = repository.jsonPayload(bvId)
                            settingsStore.setDefaultExportFormat("json")
                            output = saveOrLaunchPicker(
                                context = context,
                                settingsStore = settingsStore,
                                settings = settings,
                                payload = payload,
                                forcePicker = false,
                                onNeedPicker = {
                                    launchCreateDocument(payload)
                                }
                            )
                        } catch (exc: Exception) {
                            lastExport = null
                            output = exc.message ?: "JSON 导出失败"
                        } finally {
                            loading = false
                        }
                    }
                },
                enabled = !loading,
                modifier = Modifier.fillMaxWidth()
            ) { Text("导出 JSON") }
            Button(
                onClick = {
                    scope.launch {
                        loading = true
                        try {
                            val payload = repository.csvPayload(bvId)
                            settingsStore.setDefaultExportFormat("csv")
                            output = saveOrLaunchPicker(
                                context = context,
                                settingsStore = settingsStore,
                                settings = settings,
                                payload = payload,
                                forcePicker = false,
                                onNeedPicker = {
                                    launchCreateDocument(payload)
                                }
                            )
                        } catch (exc: Exception) {
                            lastExport = null
                            output = exc.message ?: "CSV 导出失败"
                        } finally {
                            loading = false
                        }
                    }
                },
                enabled = !loading,
                modifier = Modifier.fillMaxWidth()
            ) { Text("导出 CSV") }
        }
        Button(
            onClick = {
                scope.launch {
                    val payload = if (settings.defaultExportFormat == "json") {
                        repository.jsonPayload(bvId)
                    } else {
                        repository.csvPayload(bvId)
                    }
                    launchCreateDocument(payload)
                }
            },
            enabled = !loading,
            modifier = Modifier.fillMaxWidth()
        ) { Text("本次选择其他位置") }
        Button(
            onClick = {
                scope.launch {
                    loading = true
                    try {
                        val result = if (settings.defaultExportFormat == "json") {
                            repository.exportJson(bvId)
                        } else {
                            repository.exportCsv(bvId)
                        }
                        lastExport = result
                        shareExport(context, result)
                    } catch (exc: Exception) {
                        output = exc.message ?: "分享文件失败"
                    } finally {
                        loading = false
                    }
                }
            },
            enabled = !loading,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("生成并分享文件")
        }
        if (loading) CircularProgressIndicator()
        ExpandableText(output, collapsedMaxLines = 3)
        if (askDefaultAfterSave) {
            ExportDefaultPrompt(
                onChooseDefault = { openTreeLauncher.launch(null) },
                onAskEveryTime = {
                    scope.launch {
                        settingsStore.setAskExportLocationEveryTime(true)
                        askDefaultAfterSave = false
                        output = "后续导出将继续询问保存位置"
                    }
                },
                onDismiss = { askDefaultAfterSave = false }
            )
        }
        }
    }
}

@Composable
private fun SettingsPage(
    repository: MonitorRepository,
    settingsStore: AutoRefreshSettingsStore,
    autoRefreshScheduler: AutoRefreshScheduler
) {
    val context = LocalContext.current
    val settings by settingsStore.settings.collectAsStateWithLifecycle(initialValue = AutoRefreshSettings())
    val workInfo by autoRefreshScheduler.workInfoFlow().collectAsStateWithLifecycle(initialValue = null)
    val scope = rememberCoroutineScope()
    var status by remember { mutableStateOf<String?>(null) }
    var testRunning by remember { mutableStateOf(false) }
    var bulkRunning by remember { mutableStateOf(false) }
    var pendingExchangeExport by remember { mutableStateOf<ByteArray?>(null) }
    var exchangePreview by remember { mutableStateOf<HistoryImportPreview?>(null) }
    var exchangeResult by remember { mutableStateOf<HistoryImportReport?>(null) }
    var exchangeImportRunning by remember { mutableStateOf(false) }
    var notificationPermissionGranted by remember {
        mutableStateOf(MonitorNotificationManager.permissionGranted(context))
    }
    val notificationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        notificationPermissionGranted = granted
        scope.launch {
            settingsStore.setNotificationPermissionPrompted(true)
            if (granted) {
                settingsStore.setNotificationsEnabled(true)
                status = "通知权限已开启"
            } else {
                settingsStore.setNotificationsEnabled(false)
                status = "未开启通知权限，核心监控仍可使用"
            }
        }
    }
    val defaultTreeLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocumentTree()
    ) { uri ->
        if (uri == null) {
            status = "未选择默认导出目录"
            return@rememberLauncherForActivityResult
        }
        scope.launch {
            try {
                context.contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
                )
                settingsStore.setDefaultExportTreeUri(uri.toString())
                status = "已设置默认导出目录"
            } catch (exc: Exception) {
                status = "默认目录授权失败：${exc.message ?: exc.javaClass.simpleName}"
            }
        }
    }

    val createExchangeLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/zip")
    ) { uri ->
        val bytes = pendingExchangeExport
        pendingExchangeExport = null
        if (uri != null && bytes != null) scope.launch {
            status = runCatching {
                context.contentResolver.openOutputStream(uri, "w")?.use { it.write(bytes) }
                    ?: error("无法写入系统保存位置")
                "历史交换包导出成功：${bytes.size} bytes"
            }.getOrElse { "导出失败：${it.message}" }
        }
    }
    val openExchangeLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri == null) {
            exchangeImportRunning = false
            status = null
        } else scope.launch {
            exchangeImportRunning = true
            status = "正在读取历史记录"
            val previewResult = runCatching {
                val bytes = context.contentResolver.openInputStream(uri)?.use { input ->
                    val output = java.io.ByteArrayOutputStream()
                    val buffer = ByteArray(8192)
                    var total = 0L
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        total += count
                        require(total <= HistoryExchangeCodec.MAX_ZIP_BYTES) { "ZIP 超过 100MB 限制" }
                        output.write(buffer, 0, count)
                    }
                    output.toByteArray()
                } ?: error("无法读取所选文件")
                status = "正在校验历史记录"
                repository.previewHistoryExchange(bytes)
            }
            previewResult.onSuccess {
                exchangePreview = it
                status = null
            }.onFailure {
                exchangePreview = null
                status = "无法导入：${it.message ?: "文件无效"}"
            }
            exchangeImportRunning = false
        }
    }

    fun updateInterval(minutes: Long) {
        if (minutes == settings.intervalMinutes) return
        scope.launch {
            val oldMinutes = settings.intervalMinutes
            try {
                settingsStore.setIntervalMinutes(minutes)
                val continuousStillActive = settings.continuousMonitoringEnabled && minutes < RefreshIntervals.MIN_WORK_MANAGER_MINUTES
                if (settings.continuousMonitoringEnabled && !continuousStillActive) {
                    settingsStore.setContinuousMonitoringEnabled(false)
                    ContinuousMonitoringService.stopForReconfigure(context)
                }
                val shortForeground = minutes < RefreshIntervals.MIN_WORK_MANAGER_MINUTES && !continuousStillActive
                val result = if (continuousStillActive || shortForeground) {
                    autoRefreshScheduler.cancelAndAwait()
                    settingsStore.recordCancelled(DeviceTime.nowIsoString())
                    if (continuousStillActive) ContinuousMonitoringService.reconfigure(context)
                    null
                } else {
                    if (settings.enabled) {
                        autoRefreshScheduler.scheduleAndAwait(minutes, settings.wifiOnly)
                        com.littletaro.bilibilimonitor.settings.AutoRefreshRegistrationResult(
                            "registered", "已更新后台调度"
                        )
                    } else AutoRefreshRegistrationController.changeInterval(minutes, settings, autoRefreshScheduler)
                }
                val applied = settings.copy(intervalMinutes = minutes, continuousMonitoringEnabled = continuousStillActive)
                val mode = if (settings.enabled) MonitoringRuntime.mode(applied) else ScheduleModes.OFF
                val effective = MonitoringRuntime.effectiveInterval(applied)
                val now = DeviceTime.nowInstant()
                settingsStore.recordRuntimeSchedule(
                    effective, mode,
                    if (settings.enabled) MonitoringRuntime.nextAt(now, effective) else null,
                    if (settings.enabled) CheckStates.WAITING else CheckStates.IDLE,
                    now.toString()
                )
                if (settings.enabled) {
                    if (!continuousStillActive) settingsStore.recordRegistered(now.toString())
                    repository.writeLog(
                        "info", "work", "auto refresh rescheduled",
                        "old=${oldMinutes}m, selected=${minutes}m, effective=${effective}m, mode=$mode, next=${MonitoringRuntime.nextAt(now, effective)}"
                    )
                }
                status = if (continuousStillActive) "持续监控已更新：${minutesLabel(minutes)}"
                else if (result?.action == "saved") "已保存间隔：${minutesLabel(minutes)}" else result?.message
            } catch (exc: Exception) {
                runCatching {
                    settingsStore.setIntervalMinutes(oldMinutes)
                    if (settings.enabled) {
                        when {
                            settings.continuousMonitoringEnabled && oldMinutes < RefreshIntervals.MIN_WORK_MANAGER_MINUTES ->
                                ContinuousMonitoringService.reconfigure(context)
                            oldMinutes < RefreshIntervals.MIN_WORK_MANAGER_MINUTES -> autoRefreshScheduler.cancel()
                            else -> autoRefreshScheduler.scheduleAndAwait(oldMinutes, settings.wifiOnly)
                        }
                        val oldEffective = MonitoringRuntime.effectiveInterval(settings)
                        val oldMode = MonitoringRuntime.mode(settings)
                        val rollbackAt = DeviceTime.nowInstant()
                        settingsStore.recordRuntimeSchedule(
                            oldEffective, oldMode, MonitoringRuntime.nextAt(rollbackAt, oldEffective),
                            CheckStates.WAITING, rollbackAt.toString()
                        )
                    }
                }
                repository.writeLog("error", "work", "interval update failed", "old=${oldMinutes}m, requested=${minutes}m, ${exc.javaClass.simpleName}")
                status = "设置未生效，已保留原间隔"
            }
        }
    }

    fun openSystemSettings(intent: Intent, fallbackMessage: String) {
        runCatching { context.startActivity(intent) }
            .onFailure { status = fallbackMessage }
    }

    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = pageContentPadding()
    ) {
        item { Text("设置", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item { Text("系统权限", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item {
            SettingsSection("权限与后台运行") {
                Text("通知权限：${if (notificationPermissionGranted) "已开启" else "未开启"}")
                Text("后台运行：${if (settings.continuousMonitoringRunning) "监控运行中" else userFacingWorkState(settings, workInfo?.state?.name)}")
                Text("电池使用限制：${BackgroundRunStatus.batteryOptimizationLabel(context)}")
                Text("手机后台设置：需要确认")
                Button(
                    onClick = {
                        openSystemSettings(
                            BackgroundRunStatus.batteryOptimizationSettingsIntent(),
                            "无法打开电池设置，请在系统设置中手动查看。"
                        )
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("减少系统限制") }
                Button(
                    onClick = {
                        openSystemSettings(
                            BackgroundRunStatus.appSettingsIntent(context),
                            "无法打开应用系统设置。"
                        )
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("检查手机后台设置") }
                Button(
                    onClick = { scope.launch { settingsStore.setBackgroundGuideSeen(false) } },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("重新查看后台运行说明") }
            }
        }
        item { Text("抓取策略", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item {
            SettingsSection("自动抓取") {
                SettingSwitchRow(
                    title = "自动抓取",
                    subtitle = "只刷新已添加视频。",
                    checked = settings.enabled,
                    onCheckedChange = { enabled: Boolean ->
                        scope.launch {
                            settingsStore.setEnabled(enabled)
                            val shortForeground = enabled && settings.intervalMinutes < RefreshIntervals.MIN_WORK_MANAGER_MINUTES
                            val result = if (shortForeground) {
                                autoRefreshScheduler.cancelAndAwait()
                                com.littletaro.bilibilimonitor.settings.AutoRefreshRegistrationResult(
                                    "foreground", "已开启前台自动抓取"
                                )
                            } else if (enabled) {
                                autoRefreshScheduler.scheduleAndAwait(settings.intervalMinutes, settings.wifiOnly)
                                com.littletaro.bilibilimonitor.settings.AutoRefreshRegistrationResult(
                                    "registered", "已开启后台自动抓取"
                                )
                            } else {
                                autoRefreshScheduler.cancelAndAwait()
                                com.littletaro.bilibilimonitor.settings.AutoRefreshRegistrationResult(
                                    "cancelled", "已取消自动抓取"
                                )
                            }
                            val now = DeviceTime.nowIsoString()
                            if (enabled) {
                                if (shortForeground) settingsStore.recordCancelled(now)
                                else settingsStore.recordRegistered(now)
                                val enabledSettings = settings.copy(enabled = true)
                                val mode = MonitoringRuntime.mode(enabledSettings)
                                val effective = MonitoringRuntime.effectiveInterval(enabledSettings)
                                settingsStore.recordRuntimeSchedule(
                                    effective, mode,
                                    MonitoringRuntime.nextAt(DeviceTime.nowInstant(), effective),
                                    CheckStates.WAITING, now
                                )
                                repository.writeLog(
                                    "info",
                                    "work",
                                    "auto refresh registered",
                                    "selected=${settings.intervalMinutes}m, effective=${RefreshIntervals.backgroundScheduleMinutes(settings.intervalMinutes)}m, wifiOnly=${settings.wifiOnly}"
                                )
                            } else {
                                settingsStore.setContinuousMonitoringEnabled(false)
                                ContinuousMonitoringService.stop(context)
                                settingsStore.recordCancelled(now)
                                settingsStore.recordRuntimeSchedule(
                                    settings.intervalMinutes, ScheduleModes.OFF, null,
                                    CheckStates.IDLE, now
                                )
                                repository.writeLog("info", "work", "auto refresh cancelled")
                            }
                            status = result.message
                        }
                    }
                )
                TimeWheelSetting(
                    title = "抓取间隔",
                    selectedLabel = minutesLabel(settings.intervalMinutes),
                    enabledLabel = if (settings.enabled) "已启用" else "未启用",
                    stateKey = "auto_refresh_interval_editor"
                ) {
                    IntervalWheelPicker(
                        selectedMinutes = settings.intervalMinutes,
                        onSelected = { updateInterval(it) }
                    )
                }
                Text(
                    "当前生效：${minutesLabel(settings.effectiveIntervalMinutes)} · ${MonitoringRuntime.modeLabel(settings.scheduleMode)}"
                )
                Text("当前状态：${userFacingWorkState(settings, workInfo?.state?.name)}")
                if (settings.intervalMinutes < RefreshIntervals.MIN_WORK_MANAGER_MINUTES) {
                    SettingSwitchRow(
                        title = "允许息屏时持续抓取",
                        subtitle = "会显示后台运行通知，并增加耗电。",
                        checked = settings.continuousMonitoringEnabled,
                        onCheckedChange = { enabled ->
                            scope.launch {
                                if (enabled && (!MonitorNotificationManager.permissionGranted(context) || !MonitorNotificationManager.channelEnabled(context))) {
                                    status = "持续监控需要可用的通知权限和通知渠道"
                                } else {
                                    settingsStore.setContinuousMonitoringEnabled(enabled)
                                    if (enabled) ContinuousMonitoringService.start(context) else ContinuousMonitoringService.stop(context)
                                    status = if (enabled) "正在启动持续监控" else "正在停止持续监控"
                                }
                            }
                        }
                    )
                    Text("持续监控：${if (settings.continuousMonitoringRunning) "运行中" else "未运行"}")
                    Text("最近结果：${settings.continuousMonitoringLastResult ?: "-"}")
                }
            }
        }
        item {
            SettingsSection("网络") {
                SettingSwitchRow(
                    title = "仅在 Wi-Fi 下抓取",
                    subtitle = if (settings.wifiOnly) "移动网络下不会执行自动刷新。" else "允许任意联网状态下执行自动刷新。",
                    checked = settings.wifiOnly,
                    onCheckedChange = { wifiOnly: Boolean ->
                        scope.launch {
                            settingsStore.setWifiOnly(wifiOnly)
                            val result = AutoRefreshRegistrationController.changeWifiOnly(
                                wifiOnly,
                                settings,
                                autoRefreshScheduler
                            )
                            if (settings.enabled) {
                                val now = DeviceTime.nowIsoString()
                                settingsStore.recordRegistered(now)
                                repository.writeLog(
                                    "info",
                                    "work",
                                    "auto refresh network constraint updated",
                                    "selected=${settings.intervalMinutes}m, effective=${RefreshIntervals.backgroundScheduleMinutes(settings.intervalMinutes)}m, wifiOnly=$wifiOnly"
                                )
                            }
                            status = result.message
                        }
                    }
                )
            }
        }
        item { Text("历史数据管理", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item {
            SettingsSection("导出设置") {
                Text("默认导出格式：${settings.defaultExportFormat.uppercase()}")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    if (settings.defaultExportFormat == "csv") {
                        Button(onClick = { scope.launch { settingsStore.setDefaultExportFormat("csv") } }) { Text("CSV") }
                    } else {
                        TextButton(onClick = { scope.launch { settingsStore.setDefaultExportFormat("csv") } }) { Text("CSV") }
                    }
                    if (settings.defaultExportFormat == "json") {
                        Button(onClick = { scope.launch { settingsStore.setDefaultExportFormat("json") } }) { Text("JSON") }
                    } else {
                        TextButton(onClick = { scope.launch { settingsStore.setDefaultExportFormat("json") } }) { Text("JSON") }
                    }
                }
                Text("保存位置：${if (settings.defaultExportTreeUri == null) "每次选择" else "已设置默认位置"}")
                Button(onClick = { defaultTreeLauncher.launch(null) }, modifier = Modifier.fillMaxWidth()) {
                    Text("选择默认导出目录")
                }
                Button(
                    onClick = {
                        scope.launch {
                            settingsStore.setDefaultExportTreeUri(null)
                            status = "已清除默认导出目录"
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("清除默认导出目录")
                }
            }
        }
        item {
            SettingsSection("跨端导入与导出") {
                Button(
                    onClick = {
                        scope.launch {
                            status = "正在生成历史交换包"
                            runCatching { repository.exportHistoryExchange("0.11.2") }
                                .onSuccess {
                                    pendingExchangeExport = it
                                    createExchangeLauncher.launch("bilibili-history-v1-${System.currentTimeMillis()}.zip")
                                }
                                .onFailure { status = "导出失败：${it.message}" }
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("导出历史记录") }
                Button(
                    onClick = { openExchangeLauncher.launch(arrayOf("application/zip", "application/octet-stream")) },
                    enabled = !exchangeImportRunning,
                    modifier = Modifier.fillMaxWidth()
                ) { Text(if (exchangeImportRunning) "正在处理" else "导入历史记录") }
            }
        }
        item {
            SettingsSection("数据提醒") {
                SettingSwitchRow(
                    title = "抓取完成后提醒",
                    subtitle = if (notificationPermissionGranted) {
                        if (settings.notificationsEnabled) "已开启，检测完成后按所选模式提醒。" else "已授权，当前未开启通知。"
                    } else {
                        "系统通知权限未开启。"
                    },
                    checked = settings.notificationsEnabled && notificationPermissionGranted,
                    onCheckedChange = { enabled: Boolean ->
                        if (!enabled) {
                            scope.launch {
                                settingsStore.setNotificationsEnabled(false)
                                status = "通知提醒已关闭"
                            }
                        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !notificationPermissionGranted) {
                            scope.launch { settingsStore.setNotificationPermissionPrompted(true) }
                            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                        } else {
                            scope.launch {
                                settingsStore.setNotificationsEnabled(true)
                                status = "通知提醒已开启"
                            }
                        }
                    }
                )
                if (!notificationPermissionGranted) Text("通知未开启")
                else if (!MonitorNotificationManager.channelEnabled(context)) Text("数据提醒被系统关闭")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                    if (settings.notificationMode == NotificationModes.EACH_REFRESH) {
                        Button(onClick = { scope.launch { settingsStore.setNotificationMode(NotificationModes.EACH_REFRESH) } }, modifier = Modifier.weight(1f)) {
                            Text("每次检测")
                        }
                    } else {
                        TextButton(onClick = { scope.launch { settingsStore.setNotificationMode(NotificationModes.EACH_REFRESH) } }, modifier = Modifier.weight(1f)) {
                            Text("每次检测")
                        }
                    }
                    if (settings.notificationMode == NotificationModes.SUMMARY) {
                        Button(onClick = { scope.launch { settingsStore.setNotificationMode(NotificationModes.SUMMARY) } }, modifier = Modifier.weight(1f)) {
                            Text("定时汇总")
                        }
                    } else {
                        TextButton(onClick = { scope.launch { settingsStore.setNotificationMode(NotificationModes.SUMMARY) } }, modifier = Modifier.weight(1f)) {
                            Text("定时汇总")
                        }
                    }
                }
                if (settings.notificationMode == NotificationModes.SUMMARY) {
                    TimeWheelSetting(
                        title = "提醒频率",
                        selectedLabel = minutesLabel(settings.notificationIntervalMinutes),
                        enabledLabel = if (settings.notificationsEnabled && notificationPermissionGranted) "已启用" else "未启用",
                        stateKey = "notification_interval_editor"
                    ) {
                        NotificationIntervalWheelPicker(
                            selectedMinutes = settings.notificationIntervalMinutes,
                            detectionMinutes = settings.intervalMinutes,
                            onSelected = { minutes ->
                                scope.launch {
                                    settingsStore.setNotificationIntervalMinutes(minutes, settings.intervalMinutes)
                                    status = "通知汇总间隔已保存：${minutesLabel(minutes)}"
                                }
                            }
                        )
                    }
                    Text("提醒频率不能快于抓取频率。")
                }
                Button(
                    onClick = {
                        notificationPermissionGranted = MonitorNotificationManager.permissionGranted(context)
                        val result = MonitorNotificationManager.sendTestNotification(context)
                        scope.launch {
                            val now = DeviceTime.nowIsoString()
                            settingsStore.recordNotificationAttempt(now, result.value)
                            repository.writeLog("info", "notification", "test notification attempt", result.value)
                            status = if (result == MonitorNotificationManager.SendResult.CHANNEL_DISABLED) {
                                "通知渠道已关闭，请打开系统通知设置"
                            } else result.value
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("发送测试通知") }
                Button(
                    onClick = {
                        openSystemSettings(
                            MonitorNotificationManager.notificationSettingsIntent(context),
                            "无法打开系统通知设置，请在系统设置中手动查找本应用。"
                        )
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("打开系统通知设置")
                }
                Text("提醒方式：${if (settings.notificationMode == NotificationModes.EACH_REFRESH) "每次抓取" else "定时汇总"}")
                Text("最近尝试：${DeviceTime.formatForDisplay(settings.lastNotificationAttemptAt)}")
                Text("最近结果：${settings.lastNotificationResult ?: "-"}")
            }
        }
        item {
            Text("版本：0.11.2", style = MaterialTheme.typography.bodySmall)
        }
        item {
        status?.let { Text(it) }
        Column(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            Button(
                onClick = {
                    scope.launch {
                        testRunning = true
                        val startedAt = DeviceTime.nowIsoString()
                        settingsStore.recordWorkerStarted(startedAt)
                        repository.writeLog("info", "work", "manual auto refresh test started")
                        try {
                            val result = repository.refreshAllExistingVideos(RefreshTrigger.AUTO)
                            val resultText = "total=${result.total}, success=${result.success}, failed=${result.failed}"
                            settingsStore.recordWorkerFinished(
                                DeviceTime.nowIsoString(),
                                resultText,
                                successDelta = result.success.toLong(),
                                failureDelta = result.failed.toLong()
                            )
                            repository.writeLog("info", "work", "manual auto refresh test finished", resultText)
                            status = "测试自动刷新完成：$resultText"
                        } catch (exc: Exception) {
                            val error = "${exc.javaClass.simpleName}: ${exc.message}"
                            settingsStore.recordWorkerFinished(
                                DeviceTime.nowIsoString(),
                                "failed",
                                error,
                                failureDelta = 1
                            )
                            repository.writeLog("error", "work", "manual auto refresh test failed", error)
                            status = "测试自动刷新失败：$error"
                        } finally {
                            testRunning = false
                        }
                    }
                },
                enabled = !testRunning && !bulkRunning,
                modifier = Modifier.fillMaxWidth()
            ) { Text(if (testRunning) "测试中" else "测试自动刷新一次") }
            Button(
                onClick = {
                    scope.launch {
                        bulkRunning = true
                        repository.writeLog("info", "work", "manual bulk refresh started")
                        try {
                            val result = repository.refreshAllExistingVideos(RefreshTrigger.MANUAL)
                            val resultText = "total=${result.total}, success=${result.success}, failed=${result.failed}"
                            repository.writeLog("info", "work", "manual bulk refresh finished", resultText)
                            status = "刷新所有已添加视频完成：$resultText"
                        } catch (exc: Exception) {
                            val error = "${exc.javaClass.simpleName}: ${exc.message}"
                            repository.writeLog("error", "work", "manual bulk refresh failed", error)
                            status = "刷新所有已添加视频失败：$error"
                        } finally {
                            bulkRunning = false
                        }
                    }
                },
                enabled = !testRunning && !bulkRunning,
                modifier = Modifier.fillMaxWidth()
            ) { Text(if (bulkRunning) "刷新中" else "刷新所有已添加视频") }
        }
        }
    }
    exchangePreview?.let { preview ->
        BackHandler { if (!exchangeImportRunning) exchangePreview = null }
        AlertDialog(
            onDismissRequest = { if (!exchangeImportRunning) exchangePreview = null },
            title = { Text("确认合并历史") },
            text = { Text("来源：${preview.sourcePlatform}\n导出时间：${preview.exportedAt}\n视频：${preview.videoCount}\n快照：${preview.snapshotCount}\n重复会跳过，冲突不会覆盖。") },
            confirmButton = {
                Button(
                    enabled = !exchangeImportRunning,
                    onClick = {
                        scope.launch {
                            exchangeImportRunning = true
                            status = "正在导入历史记录"
                            val result = runCatching { repository.importHistoryExchange(preview.packageData) }
                            result.onSuccess {
                                exchangePreview = null
                                exchangeResult = it
                                status = null
                            }.onFailure {
                                exchangePreview = null
                                status = "导入失败，原有数据未改变：${it.message ?: "未知错误"}"
                            }
                            exchangeImportRunning = false
                        }
                    }
                ) { Text(if (exchangeImportRunning) "正在导入" else "合并导入") }
            },
            dismissButton = {
                TextButton(onClick = { exchangePreview = null }, enabled = !exchangeImportRunning) { Text("取消") }
            }
        )
    }
    exchangeResult?.let { report ->
        BackHandler { exchangeResult = null }
        AlertDialog(
            onDismissRequest = { exchangeResult = null },
            title = { Text(if (HistoryImportFeedback.isComplete(report)) "导入完成" else "部分数据已导入") },
            text = {
                Text(HistoryImportFeedback.message(report))
            },
            confirmButton = { Button(onClick = { exchangeResult = null }) { Text("知道了") } }
        )
    }
}

@Composable
private fun AutoRefreshStatusBlock(settings: AutoRefreshSettings, workId: String?, workState: String?) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("自动刷新调试状态", fontWeight = FontWeight.Bold)
            Text("任务名称：${AutoRefreshScheduler.UNIQUE_WORK_NAME}")
            Text("任务 ID：${workId ?: "-"}")
            Text("系统任务状态：${workState ?: "未注册或尚未读取"}")
            Text("实际调度：${MonitoringRuntime.modeLabel(settings.scheduleMode)}")
            Text("开关：${if (settings.enabled) "已开启" else "已关闭"}")
            Text("注册：${if (settings.workRegistered) "已注册" else "未注册"}")
            Text("用户间隔：${minutesLabel(settings.intervalMinutes)}")
            Text("有效间隔：${minutesLabel(settings.effectiveIntervalMinutes)}")
            Text("下次计划：${DeviceTime.formatForDisplay(settings.nextScheduledCheckAt)}")
            Text("检查状态：${settings.checkState}")
            Text("网络约束：${if (settings.wifiOnly) "仅 Wi-Fi" else "任意联网"}")
            Text("最近注册：${DeviceTime.formatForDisplay(settings.lastRegisteredAt)}")
            Text("最近计划：${DeviceTime.formatForDisplay(settings.lastRegisteredAt)}")
            Text("最近取消：${DeviceTime.formatForDisplay(settings.lastCancelledAt)}")
            Text("最近开始：${DeviceTime.formatForDisplay(settings.lastAutoRefreshStartedAt)}")
            Text("最近结束：${DeviceTime.formatForDisplay(settings.lastAutoRefreshFinishedAt)}")
            Text("最近结果：${settings.lastAutoRefreshResult ?: "-"}")
            Text("最近错误：${settings.lastAutoRefreshError ?: "-"}")
            Text("前台服务：${if (settings.continuousMonitoringRunning) "运行中" else "未运行"}")
            Text("厂商后台权限：需要确认")
            Text("累计成功：${settings.autoRefreshSuccessCount}")
            Text("累计失败：${settings.autoRefreshFailureCount}")
        }
    }
}

private fun userFacingWorkState(settings: AutoRefreshSettings, workState: String?): String = when {
    settings.continuousMonitoringRunning -> "后台监控运行中"
    workState == "RUNNING" -> "正在抓取"
    workState == "FAILED" || settings.autoRefreshFailureCount >= 3 -> "上次抓取失败"
    settings.workRegistered || workState == "ENQUEUED" -> "等待下次抓取"
    settings.enabled -> "后台运行可能受限"
    else -> "未开启"
}

@Composable
private fun SettingsSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, fontWeight = FontWeight.Bold)
            content()
        }
    }
}

@Composable
private fun SettingSwitchRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onCheckedChange(!checked) }
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(title, fontWeight = FontWeight.Bold)
            Text(subtitle, style = MaterialTheme.typography.bodySmall)
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

@Composable
private fun TimeWheelSetting(
    title: String,
    selectedLabel: String,
    enabledLabel: String,
    stateKey: String,
    content: @Composable () -> Unit
) {
    var expanded by rememberSaveable(stateKey) { mutableStateOf(WheelEditorPolicy.defaultExpanded()) }
    BackHandler(enabled = expanded) { expanded = false }
    Card(modifier = Modifier.fillMaxWidth().animateContentSize()) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = true },
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(title, fontWeight = FontWeight.Bold)
                    Text(WheelEditorPolicy.summary(title, selectedLabel, enabledLabel), style = MaterialTheme.typography.bodySmall)
                }
                TextButton(onClick = { expanded = WheelEditorPolicy.toggle(expanded) }) {
                    Text(if (expanded) "收起" else "编辑")
                }
            }
            AnimatedVisibility(visible = expanded) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("当前选择：$selectedLabel")
                    content()
                    Button(onClick = { expanded = WheelEditorPolicy.complete() }, modifier = Modifier.fillMaxWidth()) {
                        Text("完成")
                    }
                }
            }
        }
    }
}

@Composable
private fun IntervalWheelPicker(
    selectedMinutes: Long,
    onSelected: (Long) -> Unit
) {
    WheelPicker(
        options = RefreshIntervals.allowedMinutes,
        selected = selectedMinutes,
        label = { minutesLabel(it) },
        onSelected = onSelected
    )
}

@Composable
private fun NotificationIntervalWheelPicker(
    selectedMinutes: Long,
    detectionMinutes: Long,
    onSelected: (Long) -> Unit
) {
    val options = remember(detectionMinutes) { NotificationIntervals.options(detectionMinutes) }
    WheelPicker(
        options = options,
        selected = NotificationIntervals.sanitize(selectedMinutes, detectionMinutes),
        label = { minutesLabel(it) },
        onSelected = onSelected
    )
}

@Composable
private fun WheelPicker(
    options: List<Long>,
    selected: Long,
    label: (Long) -> String,
    onSelected: (Long) -> Unit
) {
    val selectedIndex = options.indexOf(selected).takeIf { it >= 0 } ?: 0
    val listState = rememberLazyListState(initialFirstVisibleItemIndex = selectedIndex.coerceAtLeast(0))
    val scope = rememberCoroutineScope()

    LaunchedEffect(selectedIndex) {
        if (!listState.isScrollInProgress && selectedIndex >= 0) {
            listState.scrollToItem(selectedIndex)
        }
    }

    LaunchedEffect(listState, selected, options) {
        snapshotFlow { listState.isScrollInProgress }
            .distinctUntilChanged()
            .filter { scrolling -> !scrolling }
            .collect {
                val layoutInfo = listState.layoutInfo
                val viewportCenter = (layoutInfo.viewportStartOffset + layoutInfo.viewportEndOffset) / 2
                val targetIndex = layoutInfo.visibleItemsInfo
                    .minByOrNull { item -> abs((item.offset + item.size / 2) - viewportCenter) }
                    ?.index
                    ?: listState.firstVisibleItemIndex
                val boundedIndex = targetIndex.coerceIn(0, options.lastIndex)
                listState.animateScrollToItem(boundedIndex)
                val stableValue = options[boundedIndex]
                if (stableValue != selected) {
                    onSelected(stableValue)
                }
            }
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(176.dp)
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.Center)
                .fillMaxWidth()
                .height(44.dp)
                .clip(RoundedCornerShape(8.dp))
                .background(MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.42f))
        )
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            contentPadding = PaddingValues(vertical = 66.dp)
        ) {
            itemsIndexed(options) { index, minutes ->
                val isSelected = minutes == selected
                val distance = abs(index - selectedIndex)
                Text(
                    text = label(minutes),
                    style = if (isSelected) MaterialTheme.typography.titleMedium else MaterialTheme.typography.bodyLarge,
                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                    color = MaterialTheme.colorScheme.onSurface.copy(
                        alpha = when {
                            isSelected -> 1f
                            distance == 1 -> 0.66f
                            else -> 0.42f
                        }
                    ),
                    textAlign = TextAlign.Center,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(44.dp)
                        .clickable {
                            scope.launch { listState.animateScrollToItem(index) }
                            if (minutes != selected) onSelected(minutes)
                        }
                        .padding(vertical = 10.dp)
                )
            }
        }
    }
}
@Composable
private fun ExpandableSection(
    title: String,
    initiallyExpanded: Boolean,
    stateKey: String,
    content: @Composable ColumnScope.() -> Unit
) {
    var expanded by rememberSaveable(stateKey) { mutableStateOf(initiallyExpanded) }
    Card(modifier = Modifier.fillMaxWidth().animateContentSize()) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(title, fontWeight = FontWeight.Bold)
                TextButton(onClick = { expanded = !expanded }) {
                    Text(if (expanded) "收起" else "展开")
                }
            }
            AnimatedVisibility(visible = expanded) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
            }
        }
    }
}

@Composable
private fun ExpandableText(
    text: String,
    collapsedMaxLines: Int,
    fontWeight: FontWeight? = null
) {
    var expanded by rememberSaveable(text) { mutableStateOf(false) }
    val canCollapse = ExpandableTextPolicy.shouldOfferExpansion(text)
    Column(modifier = Modifier.animateContentSize()) {
        Text(
            text = text,
            fontWeight = fontWeight,
            maxLines = if (expanded || !canCollapse) Int.MAX_VALUE else collapsedMaxLines,
            overflow = TextOverflow.Ellipsis
        )
        if (canCollapse) {
            TextButton(onClick = { expanded = !expanded }) {
                Text(if (expanded) "收起" else "展开")
            }
        }
    }
}

@Composable
private fun LogFilterRow(filter: String, onFilterChange: (String) -> Unit) {
    val filters = listOf("全部", "info", "warning", "error", "手动刷新", "自动刷新", "导出")
    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
        items(filters) { item ->
            if (filter == item) {
                Button(onClick = { onFilterChange(item) }) { Text(item) }
            } else {
                TextButton(onClick = { onFilterChange(item) }) { Text(item) }
            }
        }
    }
}

@Composable
private fun ExportDefaultPrompt(
    onChooseDefault: () -> Unit,
    onAskEveryTime: () -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("设置默认导出位置？") },
        text = { Text("Android 需要你额外选择一个目录并授权，才能在后续导出中直接保存到默认位置。") },
        confirmButton = {
            TextButton(onClick = onChooseDefault) { Text("选择默认目录") }
        },
        dismissButton = {
            Row {
                TextButton(onClick = onAskEveryTime) { Text("每次询问") }
                TextButton(onClick = onDismiss) { Text("取消") }
            }
        }
    )
}

private suspend fun saveOrLaunchPicker(
    context: Context,
    settingsStore: AutoRefreshSettingsStore,
    settings: AutoRefreshSettings,
    payload: ExportPayload,
    forcePicker: Boolean,
    onNeedPicker: () -> Unit
): String {
    val treeUri = settings.defaultExportTreeUri
    if (ExportLocationPolicy.shouldLaunchPicker(treeUri, settings.askExportLocationEveryTime, forcePicker)) {
        onNeedPicker()
        return "请选择保存位置：${payload.fileName}"
    }
    return try {
        writePayloadToTree(context, Uri.parse(treeUri), payload)
    } catch (exc: SecurityException) {
        settingsStore.setDefaultExportTreeUri(null)
        onNeedPicker()
        "默认目录授权失效，请重新选择保存位置"
    } catch (exc: Exception) {
        "导出失败：${exc.message ?: exc.javaClass.simpleName}"
    }
}

private fun writePayloadToUri(context: Context, uri: Uri, payload: ExportPayload): String {
    context.contentResolver.openOutputStream(uri)?.use { stream ->
        stream.write(payload.content.toByteArray(Charsets.UTF_8))
    } ?: throw IllegalStateException("无法打开系统保存位置")
    return payload.formatSaved("系统选择位置")
}

private fun writePayloadToTree(context: Context, treeUri: Uri, payload: ExportPayload): String {
    val permissionValid = context.contentResolver.persistedUriPermissions.any {
        it.uri == treeUri && it.isWritePermission
    }
    if (!permissionValid) {
        throw SecurityException("默认目录授权不存在或已失效")
    }
    val tree = DocumentFile.fromTreeUri(context, treeUri)
        ?: throw IllegalStateException("无法访问默认导出目录")
    val targetName = uniqueDocumentName(tree, payload.fileName)
    val target = tree.createFile(payload.mimeType, targetName)
        ?: throw IllegalStateException("无法创建导出文件")
    context.contentResolver.openOutputStream(target.uri)?.use { stream ->
        stream.write(payload.content.toByteArray(Charsets.UTF_8))
    } ?: throw IllegalStateException("无法写入导出文件")
    return payload.formatSaved(targetName)
}

private fun uniqueDocumentName(tree: DocumentFile, fileName: String): String {
    val dotIndex = fileName.lastIndexOf('.')
    val base = if (dotIndex > 0) fileName.substring(0, dotIndex) else fileName
    val ext = if (dotIndex > 0) fileName.substring(dotIndex) else ""
    var candidate = fileName
    var index = 1
    while (tree.findFile(candidate) != null) {
        candidate = "${base}_$index$ext"
        index += 1
    }
    return candidate
}

private suspend fun notifyManualRefresh(
    repository: MonitorRepository,
    settingsStore: AutoRefreshSettingsStore,
    context: Context
) {
    val settings = settingsStore.settings.first()
    val outcome = MonitorNotificationManager.maybeNotifyRefreshResult(
        context,
        settings,
        RefreshAllResult(total = 1, success = 1, failed = 0),
        DeviceTime.nowInstant()
    )
    settingsStore.recordNotificationAttempt(DeviceTime.nowIsoString(), outcome.value)
    repository.writeLog("info", "notification", "manual refresh notification attempt", outcome.value)
}

private fun ExportPayload.formatSaved(location: String): String =
    "导出成功\n文件名：$fileName\n大小：$sizeBytes bytes\n时间：$exportedAt\n位置：$location"

@Composable
private fun LogCard(log: AppLogEntity) {
    Card {
        Column(Modifier.fillMaxWidth().padding(12.dp)) {
            Text("${log.level} / ${log.tag}", fontWeight = FontWeight.Bold)
            Text(log.time)
            ExpandableText(log.message, collapsedMaxLines = 2)
            log.detail?.let { ExpandableText(it, collapsedMaxLines = 2) }
        }
    }
}

@Composable
private fun EmptySelection() {
    Text("请先在首页选择一个视频")
}

private fun shareExport(context: Context, result: ExportResult) {
    val file = File(result.path)
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    val mimeType = if (result.fileName.endsWith(".json")) "application/json" else "text/csv"
    val intent = Intent(Intent.ACTION_SEND)
        .setType(mimeType)
        .putExtra(Intent.EXTRA_STREAM, uri)
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    context.startActivity(Intent.createChooser(intent, "分享导出文件"))
}

private fun ExportResult.formatForDisplay(type: String): String =
    "$type 导出成功\n文件名：$fileName\n大小：$sizeBytes bytes\n时间：$exportedAt\n路径：$path"

private fun pageContentPadding(): PaddingValues = PaddingValues(bottom = 12.dp)

private fun minutesLabel(minutes: Long): String =
    when (minutes) {
        1L -> "1m"
        3L -> "3m"
        5L -> "5m"
        10L -> "10m"
        15L -> "15m"
        30L -> "30m"
        60L -> "1h"
        120L -> "2h"
        else -> "${minutes}m"
    }

private fun minValueText(points: List<TrendPoint>): String =
    points.minOfOrNull { it.value ?: Long.MAX_VALUE }?.toString() ?: "-"

private fun maxValueText(points: List<TrendPoint>): String =
    points.maxOfOrNull { it.value ?: Long.MIN_VALUE }?.toString() ?: "-"

private fun pageLabel(page: Page, backgroundRestricted: Boolean = false): String =
    when (page) {
        Page.Home -> "首页"
        Page.Detail -> "详情"
        Page.History -> "历史"
        Page.Settings -> "设置"
        Page.Advanced -> if (backgroundRestricted) "高级 · 后台受限" else "高级"
    }
