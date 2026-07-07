package com.littletaro.bilibilimonitor.data;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class BvParserTest {
    @Test
    public void parsesPlainBvId() {
        assertEquals("BV1xx411c7mD", BvParser.INSTANCE.parse("BV1xx411c7mD"));
    }

    @Test
    public void parsesVideoUrl() {
        assertEquals(
                "BV1xx411c7mD",
                BvParser.INSTANCE.parse("https://www.bilibili.com/video/BV1xx411c7mD/?spm_id_from=333.1007")
        );
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsInvalidInput() {
        BvParser.INSTANCE.parse("hello");
    }
}
