package com.littletaro.bilibilimonitor.ui;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import java.util.Arrays;
import org.junit.Test;

public class TopNavigationModelTest {
    @Test
    public void hidesVideoPagesWhenNoVideoIsSelected() {
        assertEquals(
                Arrays.asList("首页", "回收站", "设置", "高级"),
                TopNavigationModel.INSTANCE.labels(false)
        );
    }

    @Test
    public void showsVideoPagesWhenVideoIsSelected() {
        assertEquals(
                Arrays.asList("首页", "回收站", "详情", "历史", "设置", "高级"),
                TopNavigationModel.INSTANCE.labels(true)
        );
    }

    @Test
    public void clearsSelectionWhenSelectedVideoNoLongerExists() {
        assertEquals(
                "BV1xx411c7mD",
                TopNavigationModel.INSTANCE.resolveSelection(
                        "BV1xx411c7mD",
                        Arrays.asList("BV1xx411c7mD")
                )
        );
        assertNull(
                TopNavigationModel.INSTANCE.resolveSelection(
                        "BV1xx411c7mD",
                        Arrays.asList("BV2xx411c7mD")
                )
        );
    }
}
