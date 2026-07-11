package com.littletaro.bilibilimonitor.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.junit.Test;

public class TrendCalculatorTest {
    @Test
    public void computesChronologicalDeltasForSelectedMetric() {
        List<VideoSnapshotEntity> snapshots = Arrays.asList(
                snapshot(3L, "2026-01-03T00:00:00Z", 160L, 13L),
                snapshot(1L, "2026-01-01T00:00:00Z", 100L, 10L),
                snapshot(2L, "2026-01-02T00:00:00Z", 120L, 11L)
        );

        List<TrendPoint> points = TrendCalculator.INSTANCE.points(snapshots, TrendMetric.VIEW, 20);

        assertEquals(3, points.size());
        assertEquals(Long.valueOf(100L), points.get(0).getValue());
        assertNull(points.get(0).getDelta());
        assertEquals(Long.valueOf(20L), points.get(1).getDelta());
        assertEquals(Long.valueOf(40L), points.get(2).getDelta());
    }

    @Test
    public void supportsRecentTwentyAndFiftyLimits() {
        List<VideoSnapshotEntity> snapshots = new ArrayList<>();
        for (int i = 0; i < 55; i++) {
            snapshots.add(snapshot(i, String.format("2026-01-%02dT00:00:00Z", i + 1), (long) i, (long) i));
        }

        assertEquals(20, TrendCalculator.INSTANCE.points(snapshots, TrendMetric.LIKE, 20).size());
        assertEquals(50, TrendCalculator.INSTANCE.points(snapshots, TrendMetric.LIKE, 50).size());
        assertEquals(20, TrendCalculator.INSTANCE.points(snapshots, TrendMetric.LIKE, 999).size());
    }

    @Test
    public void emptyAndSinglePointInputsAreSafe() {
        assertEquals(0, TrendCalculator.INSTANCE.points(new ArrayList<>(), TrendMetric.COIN, 20).size());

        List<TrendPoint> single = TrendCalculator.INSTANCE.points(
                Arrays.asList(snapshot(1L, "2026-01-01T00:00:00Z", 100L, 1L)),
                TrendMetric.FAVORITE,
                20
        );

        assertEquals(1, single.size());
        assertNull(single.get(0).getDelta());
    }

    @Test
    public void sortsByAbsoluteTimeAcrossOffsetsAndDaylightSaving() {
        List<VideoSnapshotEntity> snapshots = Arrays.asList(
                snapshot(2L, "2026-03-08T03:30:00-04:00", 200L, 2L),
                snapshot(1L, "2026-03-08T07:00:00Z", 100L, 1L),
                snapshot(3L, "2026-03-08T16:45:00+09:00", 300L, 3L)
        );

        List<TrendPoint> points = TrendCalculator.INSTANCE.points(snapshots, TrendMetric.VIEW, 20);

        assertEquals(Long.valueOf(100L), points.get(0).getValue());
        assertEquals(Long.valueOf(200L), points.get(1).getValue());
        assertEquals(Long.valueOf(300L), points.get(2).getValue());
    }

    private static VideoSnapshotEntity snapshot(long id, String time, Long view, Long like) {
        return new VideoSnapshotEntity(
                id,
                "BV1xx411c7mD",
                time,
                view,
                null,
                5L,
                2L,
                1L,
                null,
                like,
                "https://www.bilibili.com/video/BV1xx411c7mD/",
                "success",
                null
        );
    }
}
