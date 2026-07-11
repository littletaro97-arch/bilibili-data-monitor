package com.littletaro.bilibilimonitor.ui;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class AdvancedPageModelTest {
    @Test
    public void emptySelectionShowsEmptyExportMessage() {
        AdvancedPageState state = AdvancedPageModel.INSTANCE.from(null);

        assertFalse(state.getShowExportPanel());
        assertTrue(state.getShowEmptyExportMessage());
    }

    @Test
    public void selectedVideoShowsExportPanel() {
        AdvancedPageState state = AdvancedPageModel.INSTANCE.from("BV1xx411c7mD");

        assertTrue(state.getShowExportPanel());
        assertFalse(state.getShowEmptyExportMessage());
    }
}
