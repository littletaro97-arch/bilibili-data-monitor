package com.littletaro.bilibilimonitor.data;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class ExportFileNamerTest {
    @Test
    public void exportNameIncludesBvTypeAndExtension() {
        String name = ExportFileNamer.INSTANCE.build("BV1xx411c7mD", "title", "历史数据", "csv");

        assertTrue(name.startsWith("BV1xx411c7mD_title_历史数据_"));
        assertTrue(name.endsWith(".csv"));
    }

    @Test
    public void exportNameRemovesIllegalPathCharactersAndLimitsTitle() {
        String name = ExportFileNamer.INSTANCE.build(
                "BV1xx411c7mD",
                "a/b:c*d?e\"f<g>h|veryveryveryveryveryverylong",
                "历史数据",
                "json"
        );

        assertFalse(name.contains("/"));
        assertFalse(name.contains(":"));
        assertFalse(name.contains("*"));
        assertFalse(name.contains("?"));
        assertTrue(name.endsWith(".json"));
        assertTrue(name.length() < 90);
    }
}
