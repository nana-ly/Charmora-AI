package com.client.shopguide.network;

import androidx.annotation.NonNull;

import com.client.shopguide.RetrofitClient;
import com.client.shopguide.model.RecommendResponse;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.reflect.TypeToken;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.lang.reflect.Type;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;

/**
 * SSE 流式对话客户端，对接 POST /chat/stream。
 * 事件：start → delta → items → state → done；异常时 start → error → done。
 */
public class ChatSseClient {

    public interface StreamListener {
        void onTextDelta(@NonNull String content);

        void onItems(@NonNull List<RecommendResponse.Item> items, int resultCount);

        /** state 事件原始 JSON，包含 action/intent/result_count 等字段 */
        void onState(@NonNull String stateJson);

        void onDone();

        void onError(@NonNull String message);

        /** SSE 不可用（如 404）时回退到 REST /chat */
        void onFallbackToRest();
    }

    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    private static final Gson GSON = new Gson();
    private static final Type ITEM_LIST_TYPE = new TypeToken<List<RecommendResponse.Item>>() {
    }.getType();

    private final OkHttpClient okHttpClient;
    private final String baseUrl;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private Call activeCall;

    public ChatSseClient() {
        RetrofitClient client = RetrofitClient.getInstance();
        this.okHttpClient = client.getOkHttpClient();
        this.baseUrl = client.getBaseUrl();
    }

    public void streamChat(String sessionId, String message, StreamListener listener) {
        cancel();

        JsonObject body = new JsonObject();
        body.addProperty("session_id", sessionId);
        body.addProperty("message", message);

        Request request = new Request.Builder()
                .url(baseUrl + "chat/stream")
                .post(RequestBody.create(body.toString(), JSON))
                .header("Accept", "text/event-stream")
                .build();

        activeCall = okHttpClient.newCall(request);
        activeCall.enqueue(new Callback() {
            @Override
            public void onFailure(@NonNull Call call, @NonNull IOException e) {
                if (call.isCanceled()) {
                    return;
                }
                listener.onError("网络错误：" + e.getMessage());
            }

            @Override
            public void onResponse(@NonNull Call call, @NonNull Response response) {
                if (call.isCanceled()) {
                    response.close();
                    return;
                }

                if (response.code() == 404 || response.code() == 405) {
                    response.close();
                    listener.onFallbackToRest();
                    return;
                }

                if (!response.isSuccessful()) {
                    response.close();
                    listener.onError("服务异常：" + response.code());
                    return;
                }

                ResponseBody responseBody = response.body();
                if (responseBody == null) {
                    listener.onError("响应为空");
                    return;
                }

                executor.execute(() -> parseSseStream(responseBody, listener));
            }
        });
    }

    private void parseSseStream(ResponseBody responseBody, StreamListener listener) {
        String eventName = "message";
        StringBuilder dataBuilder = new StringBuilder();

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(responseBody.byteStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.startsWith("event:")) {
                    eventName = line.substring(6).trim();
                } else if (line.startsWith("data:")) {
                    if (dataBuilder.length() > 0) {
                        dataBuilder.append('\n');
                    }
                    dataBuilder.append(line.substring(5).trim());
                } else if (line.isEmpty() && dataBuilder.length() > 0) {
                    dispatchEvent(eventName, dataBuilder.toString(), listener);
                    eventName = "message";
                    dataBuilder.setLength(0);
                }
            }

            if (dataBuilder.length() > 0) {
                dispatchEvent(eventName, dataBuilder.toString(), listener);
            }
        } catch (IOException e) {
            listener.onError("流读取失败：" + e.getMessage());
        } finally {
            responseBody.close();
        }
    }

    private void dispatchEvent(String eventName, String data, StreamListener listener) {
        if ("done".equals(eventName)) {
            listener.onDone();
            return;
        }

        if ("error".equals(eventName)) {
            listener.onError(parseErrorMessage(data));
            return;
        }

        if ("start".equals(eventName)) {
            return;
        }

        if ("state".equals(eventName)) {
            try {
                JsonObject outer = GSON.fromJson(data, JsonObject.class);
                if (outer != null && outer.has("state")) {
                    JsonObject st = outer.getAsJsonObject("state");
                    listener.onState(st.toString());
                }
            } catch (Exception ignored) {}
            return;
        }

        JsonObject json;
        try {
            json = GSON.fromJson(data, JsonObject.class);
        } catch (Exception e) {
            return;
        }

        if (json == null) {
            return;
        }

        if ("delta".equals(eventName) && json.has("text")) {
            listener.onTextDelta(json.get("text").getAsString());
            return;
        }

        if ("items".equals(eventName) && json.has("items")) {
            List<RecommendResponse.Item> items = GSON.fromJson(json.get("items"), ITEM_LIST_TYPE);
            if (items != null) {
                int resultCount = 0;
                if (json.has("result_count") && !json.get("result_count").isJsonNull()) {
                    try {
                        resultCount = json.get("result_count").getAsInt();
                    } catch (Exception ignored) {
                    }
                }
                listener.onItems(items, resultCount);
            }
        }
    }

    private String parseErrorMessage(String data) {
        try {
            JsonObject json = GSON.fromJson(data, JsonObject.class);
            if (json != null && json.has("message")) {
                return json.get("message").getAsString();
            }
        } catch (Exception ignored) {
        }
        return data;
    }

    public void cancel() {
        if (activeCall != null) {
            activeCall.cancel();
            activeCall = null;
        }
    }
}
