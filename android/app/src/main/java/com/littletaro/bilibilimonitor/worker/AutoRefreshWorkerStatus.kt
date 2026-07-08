package com.littletaro.bilibilimonitor.worker

import com.littletaro.bilibilimonitor.data.RefreshAllResult

object AutoRefreshWorkerStatus {
    fun finished(result: RefreshAllResult): String =
        "total=${result.total}, success=${result.success}, failed=${result.failed}"

    fun failed(exc: Exception): String =
        "${exc.javaClass.simpleName}: ${exc.message}; no immediate retry"
}
