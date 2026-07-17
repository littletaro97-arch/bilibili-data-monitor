package com.littletaro.bilibilimonitor

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Rule
import org.junit.Test

class MainActivityUiTest {
    @get:Rule val rule = createAndroidComposeRule<MainActivity>()

    @Test fun homeAndAdvancedNavigationAreVisible() {
        rule.onNodeWithText("首页").assertIsDisplayed()
        rule.onNodeWithText("高级", substring = true).assertIsDisplayed()
    }

    @Test fun settingsExposeThreeUserFacingGroupsAndVersion() {
        rule.onNodeWithText("设置").performClick()
        rule.onNodeWithText("系统权限").assertExists()
        rule.onNodeWithText("抓取策略").assertExists()
        rule.onNodeWithText("历史数据管理").assertExists()
        rule.onNodeWithText("版本：0.12.3").assertExists()
    }
}
