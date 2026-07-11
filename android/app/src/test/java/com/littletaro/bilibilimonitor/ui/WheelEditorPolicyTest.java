package com.littletaro.bilibilimonitor.ui;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class WheelEditorPolicyTest {
    @Test
    public void wheelEditorStartsCollapsed() {
        assertFalse(WheelEditorPolicy.defaultExpanded());
    }

    @Test
    public void toggleAndCompleteHandleExpandedState() {
        assertTrue(WheelEditorPolicy.toggle(false));
        assertFalse(WheelEditorPolicy.toggle(true));
        assertFalse(WheelEditorPolicy.complete());
    }

    @Test
    public void summaryContainsOnlyCompactInformation() {
        String summary = WheelEditorPolicy.summary("检测间隔", "15 分钟", "已启用");

        assertTrue(summary.contains("检测间隔"));
        assertTrue(summary.contains("15 分钟"));
        assertTrue(summary.contains("已启用"));
    }
}
