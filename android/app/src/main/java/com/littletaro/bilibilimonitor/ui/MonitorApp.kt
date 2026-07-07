package com.littletaro.bilibilimonitor.ui

import android.content.Intent
import android.content.Context
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.littletaro.bilibilimonitor.data.AppLogEntity
import com.littletaro.bilibilimonitor.data.ExportResult
import com.littletaro.bilibilimonitor.data.MonitorRepository
import com.littletaro.bilibilimonitor.data.RefreshTrigger
import com.littletaro.bilibilimonitor.data.TrendCalculator
import com.littletaro.bilibilimonitor.data.TrendMetric
import com.littletaro.bilibilimonitor.data.TrendPoint
import com.littletaro.bilibilimonitor.data.VideoEntity
import com.littletaro.bilibilimonitor.data.VideoSnapshotEntity
import com.littletaro.bilibilimonitor.settings.AutoRefreshSettings
import com.littletaro.bilibilimonitor.settings.AutoRefreshSettingsStore
import com.littletaro.bilibilimonitor.settings.RefreshIntervals
import com.littletaro.bilibilimonitor.worker.AutoRefreshScheduler
import kotlinx.coroutines.launch
import java.io.File

private enum class Page {
    Home,
    Detail,
    History,
    Export,
    Logs,
    Settings
}

@Composable
fun MonitorApp(
    repository: MonitorRepository,
    settingsStore: AutoRefreshSettingsStore,
    autoRefreshScheduler: AutoRefreshScheduler
) {
    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            var page by remember { mutableStateOf(Page.Home) }
            var selectedBvId by remember { mutableStateOf<String?>(null) }
            Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
                Text("B站数据监控 Android MVP", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                NavRow(page, selectedBvId != null) { page = it }
                Spacer(Modifier.height(12.dp))
                when (page) {
                    Page.Home -> HomePage(repository) {
                        selectedBvId = it
                        page = Page.Detail
                    }
                    Page.Detail -> selectedBvId?.let { DetailPage(repository, it) } ?: EmptySelection()
                    Page.History -> selectedBvId?.let { HistoryPage(repository, it) } ?: EmptySelection()
                    Page.Export -> selectedBvId?.let { ExportPage(repository, it) } ?: EmptySelection()
                    Page.Logs -> LogsPage(repository)
                    Page.Settings -> SettingsPage(repository, settingsStore, autoRefreshScheduler)
                }
            }
        }
    }
}

@Composable
private fun NavRow(current: Page, hasSelection: Boolean, onSelect: (Page) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        TextButton(onClick = { onSelect(Page.Home) }) { Text(if (current == Page.Home) "首页 *" else "首页") }
        TextButton(onClick = { onSelect(Page.Detail) }, enabled = hasSelection) { Text("详情") }
        TextButton(onClick = { onSelect(Page.History) }, enabled = hasSelection) { Text("历史") }
        TextButton(onClick = { onSelect(Page.Export) }, enabled = hasSelection) { Text("导出") }
        TextButton(onClick = { onSelect(Page.Logs) }) { Text("日志") }
        TextButton(onClick = { onSelect(Page.Settings) }) { Text("设置") }
    }
}

@Composable
private fun HomePage(repository: MonitorRepository, onOpenVideo: (String) -> Unit) {
    val videos by repository.videos.collectAsStateWithLifecycle(initialValue = emptyList())
    val scope = rememberCoroutineScope()
    var input by remember { mutableStateOf("") }
    var status by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        OutlinedTextField(
            value = input,
            onValueChange = { input = it },
            label = { Text("BV 号或 Bilibili 视频链接") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
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
                enabled = input.isNotBlank() && !loading
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
                                onOpenVideo(bvId)
                                "刷新完成 $bvId"
                            }.getOrElse { it.message ?: "刷新失败" }
                        } finally {
                            loading = false
                        }
                    }
                },
                enabled = input.isNotBlank() && !loading
            ) {
                Text("刷新数据")
            }
            if (loading) CircularProgressIndicator()
        }
        status?.let { Text(it) }
        Text("最近视频", style = MaterialTheme.typography.titleMedium)
        if (videos.isEmpty()) {
            Text("暂无视频，请先输入 BV 号或视频链接")
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(videos) { video ->
                    VideoCard(video, onOpenVideo)
                }
            }
        }
    }
}

@Composable
private fun VideoCard(video: VideoEntity, onOpenVideo: (String) -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(
                video.title ?: "未刷新标题",
                fontWeight = FontWeight.Bold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
            Text("BV: ${video.bvId}")
            Text("UP: ${video.authorName ?: "未知"}")
            Button(onClick = { onOpenVideo(video.bvId) }) {
                Text("打开")
            }
        }
    }
}

@Composable
private fun DetailPage(repository: MonitorRepository, bvId: String) {
    val videos by repository.videos.collectAsStateWithLifecycle(initialValue = emptyList())
    val latest by repository.latestSnapshot(bvId).collectAsStateWithLifecycle(initialValue = null)
    val video = videos.firstOrNull { it.bvId == bvId }
    val scope = rememberCoroutineScope()
    var message by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("视频详情", style = MaterialTheme.typography.titleMedium)
        Text(
            "标题：${video?.title ?: "未刷新"}",
            maxLines = 3,
            overflow = TextOverflow.Ellipsis
        )
        Text("UP：${video?.authorName ?: "未知"}")
        Text("BV：$bvId")
        Text("aid：${video?.aid ?: "-"}")
        Text("发布时间：${video?.pubdate ?: "-"}")
        Button(
            onClick = {
                scope.launch {
                    loading = true
                    try {
                        repository.refresh(bvId, RefreshTrigger.MANUAL)
                        message = "刷新请求已完成，请查看最新快照"
                    } finally {
                        loading = false
                    }
                }
            },
            enabled = !loading
        ) {
            Text("手动刷新")
        }
        if (loading) CircularProgressIndicator()
        message?.let { Text(it) }
        SnapshotBlock(latest)
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
            Text("采集时间：${snapshot.collectedAt}")
            Text("状态：${snapshot.fetchStatus}")
            Text("错误：${snapshot.errorMessage ?: "-"}")
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

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("趋势和历史快照", style = MaterialTheme.typography.titleMedium)
        if (snapshots.isEmpty()) {
            Text("暂无历史快照，请先手动刷新")
            return@Column
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
            TrendMetric.entries.forEach { item ->
                TextButton(onClick = { metric = item }) {
                    Text(if (metric == item) "${item.label} *" else item.label)
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("最近")
            TextButton(onClick = { limit = 20 }) { Text(if (limit == 20) "20 *" else "20") }
            TextButton(onClick = { limit = 50 }) { Text(if (limit == 50) "50 *" else "50") }
            Text("条")
        }
        TrendChart(trendPoints, metric)
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(trendPoints.reversed()) { point ->
                TrendPointCard(point, metric)
            }
            items(snapshots) { snapshot ->
                Card {
                    Column(Modifier.fillMaxWidth().padding(12.dp)) {
                        Text(snapshot.collectedAt, fontWeight = FontWeight.Bold)
                        Text("播放 ${snapshot.viewCount ?: "-"} / 点赞 ${snapshot.likeCount ?: "-"} / 状态 ${snapshot.fetchStatus}")
                        snapshot.errorMessage?.let { Text("错误：$it") }
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
            Canvas(modifier = Modifier.fillMaxWidth().height(160.dp)) {
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
                offsets.forEach { offset ->
                    drawCircle(pointColor, radius = 5f, center = offset)
                }
            }
            Text("最小 ${minValueText(validPoints)} / 最大 ${maxValueText(validPoints)}")
        }
    }
}

@Composable
private fun TrendPointCard(point: TrendPoint, metric: TrendMetric) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(point.collectedAt, fontWeight = FontWeight.Bold)
            Text("${metric.label}：${point.value ?: "-"} / 增量：${point.delta?.toString() ?: "-"}")
        }
    }
}

@Composable
private fun ExportPage(repository: MonitorRepository, bvId: String) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var output by remember { mutableStateOf("尚未导出") }
    var lastExport by remember { mutableStateOf<ExportResult?>(null) }
    var loading by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("导出 $bvId")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = {
                    scope.launch {
                        loading = true
                        try {
                            val result = repository.exportJson(bvId)
                            lastExport = result
                            output = result.formatForDisplay("JSON")
                        } catch (exc: Exception) {
                            lastExport = null
                            output = exc.message ?: "JSON 导出失败"
                        } finally {
                            loading = false
                        }
                    }
                },
                enabled = !loading
            ) { Text("导出 JSON") }
            Button(
                onClick = {
                    scope.launch {
                        loading = true
                        try {
                            val result = repository.exportCsv(bvId)
                            lastExport = result
                            output = result.formatForDisplay("CSV")
                        } catch (exc: Exception) {
                            lastExport = null
                            output = exc.message ?: "CSV 导出失败"
                        } finally {
                            loading = false
                        }
                    }
                },
                enabled = !loading
            ) { Text("导出 CSV") }
        }
        Button(
            onClick = {
                lastExport?.let { result ->
                    shareExport(context, result)
                }
            },
            enabled = lastExport != null && !loading
        ) {
            Text("分享文件")
        }
        if (loading) CircularProgressIndicator()
        Text(output)
    }
}

@Composable
private fun LogsPage(repository: MonitorRepository) {
    val logs by repository.logs.collectAsStateWithLifecycle(initialValue = emptyList())
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("最近 200 条日志，按时间倒序")
        if (logs.isEmpty()) {
            Text("暂无日志")
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(logs) { log ->
                    LogCard(log)
                }
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
    val settings by settingsStore.settings.collectAsStateWithLifecycle(initialValue = AutoRefreshSettings())
    val scope = rememberCoroutineScope()

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("低频自动刷新", style = MaterialTheme.typography.titleMedium)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(if (settings.enabled) "已开启" else "已关闭")
            Switch(
                checked = settings.enabled,
                onCheckedChange = { enabled ->
                    scope.launch {
                        settingsStore.setEnabled(enabled)
                        if (enabled) {
                            autoRefreshScheduler.schedule(settings.intervalMinutes, settings.wifiOnly)
                            repository.writeLog("info", "work", "auto refresh registered", "interval=${settings.intervalMinutes}m, wifiOnly=${settings.wifiOnly}")
                        } else {
                            autoRefreshScheduler.cancel()
                            repository.writeLog("info", "work", "auto refresh cancelled")
                        }
                    }
                }
            )
        }
        Text("刷新范围：仅刷新你已经添加的视频，不发现新视频，不采集评论/弹幕，不处理登录、验证码或风控。")
        Text("Android 可能延迟或合并后台任务；这里是低频趋势刷新，不是实时监控。")
        Text("最近一次自动刷新：${settings.lastAutoRefreshAt ?: "尚无记录"}")
        Text("间隔")
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), modifier = Modifier.fillMaxWidth()) {
            RefreshIntervals.allowedMinutes.forEach { minutes ->
                TextButton(
                    onClick = {
                        scope.launch {
                            settingsStore.setIntervalMinutes(minutes)
                            if (settings.enabled) {
                                autoRefreshScheduler.schedule(minutes, settings.wifiOnly)
                                repository.writeLog("info", "work", "auto refresh rescheduled", "interval=${minutes}m, wifiOnly=${settings.wifiOnly}")
                            }
                        }
                    }
                ) {
                    Text(if (settings.intervalMinutes == minutes) "${minutesLabel(minutes)} *" else minutesLabel(minutes))
                }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("仅 Wi-Fi")
            Switch(
                checked = settings.wifiOnly,
                onCheckedChange = { wifiOnly ->
                    scope.launch {
                        settingsStore.setWifiOnly(wifiOnly)
                        if (settings.enabled) {
                            autoRefreshScheduler.schedule(settings.intervalMinutes, wifiOnly)
                            repository.writeLog("info", "work", "auto refresh network constraint updated", "interval=${settings.intervalMinutes}m, wifiOnly=$wifiOnly")
                        }
                    }
                }
            )
        }
    }
}

@Composable
private fun LogCard(log: AppLogEntity) {
    Card {
        Column(Modifier.fillMaxWidth().padding(12.dp)) {
            Text("${log.level} / ${log.tag}", fontWeight = FontWeight.Bold)
            Text(log.time)
            Text(log.message)
            log.detail?.let { Text(it) }
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

private fun minutesLabel(minutes: Long): String =
    when (minutes) {
        60L -> "1h"
        180L -> "3h"
        360L -> "6h"
        else -> "${minutes}m"
    }

private fun minValueText(points: List<TrendPoint>): String =
    points.minOfOrNull { it.value ?: Long.MAX_VALUE }?.toString() ?: "-"

private fun maxValueText(points: List<TrendPoint>): String =
    points.maxOfOrNull { it.value ?: Long.MIN_VALUE }?.toString() ?: "-"
