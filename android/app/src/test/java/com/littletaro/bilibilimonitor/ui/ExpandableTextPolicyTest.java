package com.littletaro.bilibilimonitor.ui;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class ExpandableTextPolicyTest {
    @Test
    public void shortSingleLineTextDoesNotNeedExpansion() {
        assertFalse(ExpandableTextPolicy.INSTANCE.shouldOfferExpansion("短状态"));
    }

    @Test
    public void longTextCanBeExpanded() {
        assertTrue(ExpandableTextPolicy.INSTANCE.shouldOfferExpansion(
                "这是一段很长的日志内容，用于验证长文本默认折叠但仍然可以展开查看完整内容，避免一条错误日志占满整个页面并影响滚动。"
        ));
    }

    @Test
    public void multilineTextCanBeExpanded() {
        assertTrue(ExpandableTextPolicy.INSTANCE.shouldOfferExpansion("第一行\n第二行"));
    }
}
