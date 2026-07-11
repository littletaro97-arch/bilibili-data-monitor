package com.littletaro.bilibilimonitor.ui;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.littletaro.bilibilimonitor.data.HistoryImportReport;
import org.junit.Test;

public class InteractionPoliciesTest {
    @Test
    public void backClosesOverlayThenReturnsHomeThenUsesSystemDefault() {
        assertEquals(BackAction.CLOSE_OVERLAY, NavigationBackPolicy.INSTANCE.action(true, false));
        assertEquals(BackAction.GO_HOME, NavigationBackPolicy.INSTANCE.action(false, false));
        assertEquals(BackAction.SYSTEM_DEFAULT, NavigationBackPolicy.INSTANCE.action(false, true));
    }

    @Test
    public void importFeedbackReportsCountsAndPartialOutcome() {
        HistoryImportReport complete = new HistoryImportReport(3, 128, 12, 0, 0);
        HistoryImportReport partial = new HistoryImportReport(1, 2, 4, 1, 1);

        assertTrue(HistoryImportFeedback.INSTANCE.isComplete(complete));
        assertTrue(HistoryImportFeedback.INSTANCE.message(complete).contains("新增 3 个视频、128 条历史记录"));
        assertFalse(HistoryImportFeedback.INSTANCE.isComplete(partial));
        assertTrue(HistoryImportFeedback.INSTANCE.message(partial).contains("另有 2 条数据未导入"));
    }
}
