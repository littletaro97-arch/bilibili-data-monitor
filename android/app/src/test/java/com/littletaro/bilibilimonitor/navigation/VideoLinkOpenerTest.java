package com.littletaro.bilibilimonitor.navigation;

import static org.junit.Assert.*;

import java.util.ArrayList;
import java.util.List;
import org.junit.Test;

public class VideoLinkOpenerTest {
    @Test public void directedSuccessDoesNotOpenBrowser() {
        FakeStarter fake = new FakeStarter(true, true);
        VideoOpenResult result = new VideoLinkOpener(fake).open("BV1xx411c7mD");
        assertTrue(result.getSucceeded());
        assertEquals(1, fake.packages.size());
        assertEquals(VideoLinkOpener.BILIBILI_PACKAGE, fake.packages.get(0));
    }

    @Test public void directedFailureFallsBackWithoutPackage() {
        FakeStarter fake = new FakeStarter(false, true);
        VideoOpenResult result = new VideoLinkOpener(fake).open("BV1xx411c7mD");
        assertTrue(result.getSucceeded());
        assertEquals(2, fake.packages.size());
        assertNull(fake.packages.get(1));
        assertEquals("https://www.bilibili.com/video/BV1xx411c7mD", result.getUri());
    }

    @Test public void bothFailuresReturnUserError() {
        VideoOpenResult result = new VideoLinkOpener(new FakeStarter(false, false)).open("BV1xx411c7mD");
        assertFalse(result.getSucceeded());
        assertEquals("未找到可以打开该视频链接的应用", result.getErrorMessage());
    }

    @Test(expected = IllegalArgumentException.class)
    public void invalidBvIsRejected() {
        new VideoLinkOpener(new FakeStarter(true, true)).open("bad");
    }

    private static class FakeStarter implements VideoIntentStarter {
        final boolean directed;
        final boolean generic;
        final List<String> packages = new ArrayList<>();
        FakeStarter(boolean directed, boolean generic) { this.directed = directed; this.generic = generic; }
        @Override public VideoOpenAttempt start(String uri, String packageName) {
            packages.add(packageName);
            boolean success = packageName == null ? generic : directed;
            return new VideoOpenAttempt(packageName == null ? "generic_https" : "bilibili_app", packageName != null, success, success ? null : "ActivityNotFoundException");
        }
    }
}
