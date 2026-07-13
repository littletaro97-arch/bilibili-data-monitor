package com.littletaro.bilibilimonitor.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CoverUrlPolicyTest {
    @Test fun acceptsOnlyHttpsBilibiliImageHosts() {
        assertEquals("https://i0.hdslb.com/bfs/archive/cover.jpg", CoverUrlPolicy.acceptedOrNull("https://i0.hdslb.com/bfs/archive/cover.jpg"))
        assertNull(CoverUrlPolicy.acceptedOrNull("http://i0.hdslb.com/cover.jpg"))
        assertNull(CoverUrlPolicy.acceptedOrNull("https://example.com/cover.jpg"))
        assertNull(CoverUrlPolicy.acceptedOrNull("file:///data/local/tmp/cover.jpg"))
    }
}
