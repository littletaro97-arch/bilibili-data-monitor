package com.littletaro.bilibilimonitor.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.util.Arrays;
import org.junit.Test;

public class SnapshotExporterTest {
    @Test
    public void csvHeaderUsesSharedSchemaFields() {
        assertEquals(
                Arrays.asList(
                        "platform",
                        "bv_id",
                        "aid",
                        "title",
                        "author_name",
                        "author_mid",
                        "duration",
                        "pubdate",
                        "collected_at",
                        "view_count",
                        "danmaku_count",
                        "reply_count",
                        "favorite_count",
                        "coin_count",
                        "share_count",
                        "like_count",
                        "source_url",
                        "fetch_status",
                        "error_message",
                        "capture_source"
                ),
                SnapshotExporter.Companion.getCSV_HEADER()
        );
    }

    @Test
    public void csvCellEscapesCommasQuotesAndLineBreaks() {
        assertEquals("\"a,b\"", SnapshotExporter.Companion.csvCell("a,b"));
        assertEquals("\"a\"\"b\"", SnapshotExporter.Companion.csvCell("a\"b"));
        assertTrue(SnapshotExporter.Companion.csvCell("a\nb").startsWith("\""));
        assertEquals("", SnapshotExporter.Companion.csvCell(null));
    }
}
