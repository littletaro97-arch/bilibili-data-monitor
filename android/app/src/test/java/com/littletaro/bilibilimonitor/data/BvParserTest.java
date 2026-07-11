package com.littletaro.bilibilimonitor.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

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

    @Test
    public void parsesMobileVideoUrlAndShareText() {
        assertEquals(
                "BV1xx411c7mD",
                BvParser.INSTANCE.parse("https://m.bilibili.com/video/BV1xx411c7mD?share_source=copy_web")
        );
        assertEquals(
                "BV1xx411c7mD",
                BvParser.INSTANCE.parse("我正在看【测试标题】\nhttps://www.bilibili.com/video/BV1xx411c7mD/?vd_source=abc，复制打开")
        );
    }

    @Test
    public void parsesPreciseTimeLinkAndChineseWrappedText() {
        assertEquals(
                "BV1xx411c7mD",
                BvParser.INSTANCE.parse("看看这个： https://www.bilibili.com/video/BV1xx411c7mD/?t=123.4&p=1 。")
        );
    }

    @Test
    public void extractsUrlsFromMobileShareText() {
        assertEquals(
                "https://b23.tv/abc123",
                BvParser.INSTANCE.extractUrls("复制这条链接 https://b23.tv/abc123，打开哔哩哔哩").get(0)
        );
        assertTrue(BvParser.INSTANCE.isBilibiliShortUrl("https://b23.tv/abc123"));
    }

    @Test
    public void usesFirstBilibiliIdentifierWhenMultipleLinksExist() {
        assertEquals(
                "BV1xx411c7mD",
                BvParser.INSTANCE.parse("https://example.com/a BV1xx411c7mD https://www.bilibili.com/video/BV1yy411c7mD/")
        );
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsInvalidInput() {
        BvParser.INSTANCE.parse("hello");
    }
}
