package org.questtermuxlab.vncpanel;

import android.app.Activity;
import android.os.Bundle;
import android.view.ViewGroup;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public final class MainActivity extends Activity {
    private static final String DEFAULT_BASE_URL = "http://127.0.0.1:18080";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        WebView webView = new WebView(this);
        webView.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        webView.setWebViewClient(new WebViewClient());

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        settings.setMediaPlaybackRequiresUserGesture(false);

        String baseUrl = getIntent().getStringExtra("stream_base_url");
        if (baseUrl == null || baseUrl.trim().isEmpty()) {
            baseUrl = DEFAULT_BASE_URL;
        }
        baseUrl = trimTrailingSlash(baseUrl.trim());

        setContentView(webView);
        webView.loadDataWithBaseURL(
                baseUrl + "/",
                buildViewerHtml(baseUrl),
                "text/html",
                "UTF-8",
                null);
    }

    private static String trimTrailingSlash(String value) {
        while (value.endsWith("/") && value.length() > "http://".length()) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    private static String buildViewerHtml(String baseUrl) {
        String escapedBase = escapeJs(baseUrl);
        return "<!doctype html><html><head><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                + "<style>"
                + "html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#050607;color:#e8eef2;"
                + "font-family:sans-serif;}"
                + "#frame{position:fixed;inset:0;width:100vw;height:100vh;object-fit:contain;background:#000;}"
                + "#status{position:fixed;left:10px;right:10px;bottom:8px;padding:5px 8px;"
                + "border-radius:4px;background:rgba(0,0,0,.62);font-size:12px;line-height:1.25;}"
                + "</style></head><body>"
                + "<img id=\"frame\" src=\"" + escapedBase + "/stream.mjpg\" alt=\"VNC stream\">"
                + "<div id=\"status\">connecting...</div>"
                + "<script>"
                + "const base='" + escapedBase + "';"
                + "async function tick(){"
                + "try{const r=await fetch(base+'/status.json',{cache:'no-store'});"
                + "const s=await r.json();"
                + "document.getElementById('status').textContent="
                + "(s.connected?'connected':'disconnected')+' | '+s.width+'x'+s.height"
                + "+' | frames '+s.frames+' | avg '+Number(s.average_fps||0).toFixed(2)+' fps'"
                + "+' | age '+Number(s.last_frame_age_seconds||0).toFixed(2)+'s'"
                + "+(s.last_error?' | '+s.last_error:'');"
                + "}catch(e){document.getElementById('status').textContent='status error: '+e;}}"
                + "setInterval(tick,1000);tick();"
                + "</script></body></html>";
    }

    private static String escapeJs(String value) {
        return value.replace("\\", "\\\\").replace("'", "\\'");
    }
}
