package com.littletaro.bilibilimonitor.ui;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class ExportLocationPolicyTest {
    @Test
    public void firstExportLaunchesSystemPicker() {
        assertTrue(ExportLocationPolicy.INSTANCE.shouldLaunchPicker(null, true, false));
    }

    @Test
    public void persistedDefaultDirectoryCanSaveDirectly() {
        assertFalse(ExportLocationPolicy.INSTANCE.shouldLaunchPicker("content://tree/default", false, false));
    }

    @Test
    public void forcePickerIgnoresPersistedDefaultDirectory() {
        assertTrue(ExportLocationPolicy.INSTANCE.shouldLaunchPicker("content://tree/default", false, true));
    }
}
