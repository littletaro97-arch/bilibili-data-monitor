package com.littletaro.bilibilimonitor.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import org.junit.Test;

public class BilibiliApiTest {
    @Test
    public void mapsSuccessfulViewResponse() {
        VideoSnapshotRecord record = BilibiliApi.Companion.mapViewResponse(
                "BV1xx411c7mD",
                "{"
                        + "\"code\":0,"
                        + "\"data\":{"
                        + "\"aid\":123,"
                        + "\"title\":\"Test Video\","
                        + "\"pic\":\"https://i0.hdslb.com/bfs/archive/cover.jpg\","
                        + "\"duration\":90,"
                        + "\"pubdate\":1710000000,"
                        + "\"owner\":{\"mid\":456,\"name\":\"UP\"},"
                        + "\"stat\":{"
                        + "\"view\":1000,"
                        + "\"danmaku\":20,"
                        + "\"reply\":30,"
                        + "\"favorite\":40,"
                        + "\"coin\":50,"
                        + "\"share\":60,"
                        + "\"like\":70"
                        + "}"
                        + "}"
                        + "}",
                "2026-07-07T00:00:00Z"
        );

        assertEquals("Test Video", record.getVideo().getTitle());
        assertEquals(Long.valueOf(123L), record.getVideo().getAid());
        assertEquals("UP", record.getVideo().getAuthorName());
        assertEquals("https://i0.hdslb.com/bfs/archive/cover.jpg", record.getVideo().getCoverUrl());
        assertEquals("success", record.getSnapshot().getFetchStatus());
        assertEquals(Long.valueOf(1000L), record.getSnapshot().getViewCount());
        assertNull(record.getSnapshot().getErrorMessage());
    }

    @Test
    public void failedApiCodeCreatesFailedSnapshot() {
        VideoSnapshotRecord record = BilibiliApi.Companion.mapViewResponse(
                "BV1xx411c7mD",
                "{\"code\":-400,\"message\":\"bad request\"}",
                "2026-07-07T00:00:00Z"
        );

        assertEquals("failed", record.getSnapshot().getFetchStatus());
        assertEquals("接口返回失败：code=-400, message=bad request", record.getSnapshot().getErrorMessage());
    }

    @Test
    public void loginLimitedApiCodeCreatesClearMessage() {
        VideoSnapshotRecord record = BilibiliApi.Companion.mapViewResponse(
                "BV1xx411c7mD",
                "{\"code\":-101,\"message\":\"账号未登录\"}",
                "2026-07-07T00:00:00Z"
        );

        assertEquals("failed", record.getSnapshot().getFetchStatus());
        assertEquals(
                "接口要求登录，本应用不会绕过登录限制：code=-101, message=账号未登录",
                record.getSnapshot().getErrorMessage()
        );
    }
}
