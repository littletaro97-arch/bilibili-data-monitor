package com.littletaro.bilibilimonitor.data;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.io.IOException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import okhttp3.Interceptor;
import okhttp3.OkHttpClient;
import okhttp3.Protocol;
import okhttp3.Response;
import okhttp3.ResponseBody;
import org.junit.Test;

public class BilibiliShareLinkResolverTest {
    @Test
    public void resolvesB23ShortLinkRedirectToBvId() throws Exception {
        OkHttpClient client = clientReturningRedirect("https://www.bilibili.com/video/BV1xx411c7mD/?share_source=copy");

        assertEquals(
                "BV1xx411c7mD",
                BilibiliApi.Companion.resolveSharedBvId("复制链接 https://b23.tv/abc123", client)
        );
    }

    @Test
    public void rejectsRedirectToNonBilibiliHost() {
        OkHttpClient client = clientReturningRedirect("https://example.com/video/BV1xx411c7mD/");

        try {
            BilibiliApi.Companion.resolveSharedBvId("https://b23.tv/abc123", client);
        } catch (Exception exc) {
            assertTrue(exc.getMessage().contains("非哔哩哔哩地址"));
            return;
        }
        throw new AssertionError("Expected resolver failure");
    }

    @Test
    public void reportsNetworkFailureForShortLink() {
        OkHttpClient client = clientThrowing(new UnknownHostException("offline"));

        try {
            BilibiliApi.Companion.resolveSharedBvId("https://b23.tv/abc123", client);
        } catch (Exception exc) {
            assertTrue(exc.getMessage().contains("检查网络"));
            return;
        }
        throw new AssertionError("Expected network failure");
    }

    @Test
    public void reportsTimeoutForShortLink() {
        OkHttpClient client = clientThrowing(new SocketTimeoutException("timeout"));

        try {
            BilibiliApi.Companion.resolveSharedBvId("https://b23.tv/abc123", client);
        } catch (Exception exc) {
            assertTrue(exc.getMessage().contains("超时"));
            return;
        }
        throw new AssertionError("Expected timeout failure");
    }

    private static OkHttpClient clientReturningRedirect(String location) {
        return new OkHttpClient.Builder()
                .addInterceptor(chain -> {
                    if ("b23.tv".equals(chain.request().url().host())) {
                        return new Response.Builder()
                                .request(chain.request())
                                .protocol(Protocol.HTTP_1_1)
                                .code(302)
                                .message("Found")
                                .header("Location", location)
                                .body(ResponseBody.create(new byte[0], null))
                                .build();
                    }
                    return new Response.Builder()
                            .request(chain.request())
                            .protocol(Protocol.HTTP_1_1)
                            .code(200)
                            .message("OK")
                            .body(ResponseBody.create(new byte[0], null))
                            .build();
                })
                .build();
    }

    private static OkHttpClient clientThrowing(IOException error) {
        return new OkHttpClient.Builder()
                .addInterceptor((Interceptor) chain -> {
                    throw error;
                })
                .build();
    }
}
