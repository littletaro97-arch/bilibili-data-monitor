package com.littletaro.bilibilimonitor

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test

class MainActivityUiTest {
    @get:Rule val rule = createAndroidComposeRule<MainActivity>()

    @Test fun homeAndAdvancedNavigationAreVisible() {
        rule.onNodeWithText("首页").assertIsDisplayed()
        rule.onNodeWithText("高级", substring = true).assertIsDisplayed()
    }
}
