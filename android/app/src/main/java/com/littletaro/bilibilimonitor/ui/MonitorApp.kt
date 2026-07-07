package com.littletaro.bilibilimonitor.ui

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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.littletaro.bilibilimonitor.data.AppLogEntity
import com.littletaro.bilibilimonitor.data.ExportResult
import com.littletaro.bilibilimonitor.data.MonitorRepository
import com.littletaro.bilibilimonitor.data.VideoEntity
import com.littletaro.bilibilimonitor.data.VideoSnapshotEntity
import kotlinx.coroutines.launch

private enum class Page {
    Home,
    Detail,
    History,
    Export,
    Logs
}

@Composable
fun MonitorApp(repository: MonitorRepository) {
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
                                repository.refresh(bvId)
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
                        repository.refresh(bvId)
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
    if (snapshots.isEmpty()) {
        Text("暂无历史快照，请先手动刷新")
    } else {
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
private fun ExportPage(repository: MonitorRepository, bvId: String) {
    val scope = rememberCoroutineScope()
    var output by remember { mutableStateOf("尚未导出") }
    var loading by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("导出 $bvId")
        Button(
            onClick = {
                scope.launch {
                    loading = true
                    try {
                        output = runCatching { repository.exportJson(bvId).formatForDisplay("JSON") }
                            .getOrElse { it.message ?: "JSON 导出失败" }
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
                        output = runCatching { repository.exportCsv(bvId).formatForDisplay("CSV") }
                            .getOrElse { it.message ?: "CSV 导出失败" }
                    } finally {
                        loading = false
                    }
                }
            },
            enabled = !loading
        ) { Text("导出 CSV") }
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

private fun ExportResult.formatForDisplay(type: String): String =
    "$type 导出成功\n文件名：$fileName\n时间：$exportedAt\n路径：$path"
