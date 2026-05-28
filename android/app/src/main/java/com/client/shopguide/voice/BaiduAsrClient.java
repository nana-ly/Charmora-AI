package com.client.shopguide.voice;

import com.client.shopguide.BuildConfig;

import android.util.Base64;
import android.util.Log;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * 百度语音识别 REST API 客户端
 * 文档：https://ai.baidu.com/ai-doc/SPEECH/Vk38lxily
 */
public class BaiduAsrClient {

    private static final String TAG = "BaiduAsrClient";

    // ========== 从 .env 注入的百度 AI 应用凭证 ==========
    // 在 android/.env 中填写:
    //   BAIDU_APP_ID=你的AppID
    //   BAIDU_API_KEY=你的API Key
    //   BAIDU_SECRET_KEY=你的Secret Key
    private static final String APP_ID = BuildConfig.BAIDU_APP_ID;
    private static final String API_KEY = BuildConfig.BAIDU_API_KEY;
    private static final String SECRET_KEY = BuildConfig.BAIDU_SECRET_KEY;

    // ========== API 地址 ==========
    private static final String TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token";
    private static final String ASR_URL = "https://vop.baidu.com/server_api";

    private static String cachedToken;

    /**
     * 获取百度 API access_token（带缓存）
     */
    private static String getAccessToken() throws Exception {
        if (cachedToken != null) return cachedToken;

        String urlStr = TOKEN_URL + "?grant_type=client_credentials"
                + "&client_id=" + API_KEY
                + "&client_secret=" + SECRET_KEY;

        HttpURLConnection conn = (HttpURLConnection) new URL(urlStr).openConnection();
        conn.setRequestMethod("POST");
        conn.setConnectTimeout(5000);
        conn.setReadTimeout(5000);

        String response;
        try (InputStream is = conn.getInputStream()) {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            byte[] buf = new byte[1024];
            int len;
            while ((len = is.read(buf)) != -1) {
                baos.write(buf, 0, len);
            }
            response = baos.toString("UTF-8");
        }
        conn.disconnect();

        JSONObject json = new JSONObject(response);
        cachedToken = json.getString("access_token");
        Log.d(TAG, "Token获取成功");
        return cachedToken;
    }

    /**
     * 识别 PCM 音频数据转文字
     *
     * @param pcmData   PCM 格式音频（16kHz, 16bit, 单声道）
     * @param audioLen  音频原始字节数
     * @return 识别结果文字，失败返回 null
     */
    public static String recognize(byte[] pcmData, int audioLen) throws Exception {
        String token = getAccessToken();

        // 构建请求体 JSON
        JSONObject params = new JSONObject();
        params.put("format", "pcm");
        params.put("rate", 16000);
        params.put("channel", 1);
        params.put("cuid", APP_ID);
        params.put("token", token);
        params.put("speech", Base64.encodeToString(pcmData, Base64.NO_WRAP));
        params.put("len", audioLen);
        params.put("dev_pid", 1537); // 1537 = 普通话(纯中文识别)

        // 发送 POST
        HttpURLConnection conn = (HttpURLConnection) new URL(ASR_URL).openConnection();
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Content-Type", "application/json");
        conn.setConnectTimeout(10000);
        conn.setReadTimeout(15000);
        conn.setDoOutput(true);

        byte[] body = params.toString().getBytes(StandardCharsets.UTF_8);
        try (OutputStream os = conn.getOutputStream()) {
            os.write(body);
            os.flush();
        }

        // 读取响应
        String response;
        try (InputStream is = conn.getInputStream()) {
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            byte[] buf = new byte[1024];
            int len;
            while ((len = is.read(buf)) != -1) {
                baos.write(buf, 0, len);
            }
            response = baos.toString("UTF-8");
        }
        conn.disconnect();

        Log.d(TAG, "ASR 响应: " + response);

        // 解析结果
        JSONObject json = new JSONObject(response);
        int errNo = json.optInt("err_no", -1);
        if (errNo != 0) {
            String errMsg = json.optString("err_msg", "未知错误");
            Log.e(TAG, "ASR 错误: " + errNo + " - " + errMsg);
            return null;
        }

        if (json.has("result")) {
            return json.getJSONArray("result").getString(0);
        }

        return null;
    }
}
