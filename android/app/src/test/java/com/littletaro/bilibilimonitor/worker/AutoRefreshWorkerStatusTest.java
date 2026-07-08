package com.littletaro.bilibilimonitor.worker;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.littletaro.bilibilimonitor.data.RefreshAllResult;
import org.junit.Test;

public class AutoRefreshWorkerStatusTest {
    @Test
    public void emptyVideoRunStillProducesVisibleResult() {
        String status = AutoRefreshWorkerStatus.INSTANCE.finished(new RefreshAllResult(0, 0, 0));

        assertEquals("total=0, success=0, failed=0", status);
    }

    @Test
    public void failedRunExplainsNoImmediateRetry() {
        String status = AutoRefreshWorkerStatus.INSTANCE.failed(new IllegalStateException("network down"));

        assertTrue(status.contains("IllegalStateException"));
        assertTrue(status.contains("network down"));
        assertTrue(status.contains("no immediate retry"));
    }
}
