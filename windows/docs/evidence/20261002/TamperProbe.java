import com.littletaro.bilibilimonitor.data.HistoryExchangeCodec;
import com.littletaro.bilibilimonitor.data.HistoryImportPreview;
import com.littletaro.bilibilimonitor.data.CoverUrlPolicy;
import java.nio.file.Files;
import java.nio.file.Path;
import org.json.JSONObject;
public class TamperProbe {
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]);
        boolean rejected = false;
        try { HistoryExchangeCodec.INSTANCE.preview(Files.readAllBytes(root.resolve("corrupt.zip"))); }
        catch (IllegalArgumentException expected) { rejected = true; }
        HistoryImportPreview preview = HistoryExchangeCodec.INSTANCE.preview(Files.readAllBytes(root.resolve("forged.zip")));
        long count = preview.getPackageData().getSnapshots().get(0).getViewCount();
        JSONObject result = new JSONObject().put("android_corruption_rejected",rejected)
            .put("android_forged_hashes_accepted",count == 999999L)
            .put("android_forged_view_count",count)
            .put("android_http_cover_rejected",CoverUrlPolicy.INSTANCE.acceptedOrNull("http://i1.hdslb.com/bfs/archive/5242750857121e05146d5d5b13a47a2a6dd36e98.jpg") == null)
            .put("runtime","JVM, existing v0.13.1 codec classes; matching sources unchanged since 6e050fb");
        Files.writeString(root.resolve("android-result.json"),result.toString(2));
        System.out.println(result.toString(2));
    }
}
