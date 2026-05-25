package com.client.shopguide;

import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.client.shopguide.adapter.ChatAdapter;
import com.client.shopguide.model.ChatRequest;
import com.client.shopguide.model.ChatResponse;
import com.client.shopguide.model.ChatUiMessage;
import com.client.shopguide.model.Product;
import com.client.shopguide.model.RecommendResponse;
import com.client.shopguide.network.ChatSseClient;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class MainActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "shopguide_chat";
    private static final String KEY_SESSION_ID = "session_id";
    private static final String WELCOME_MESSAGE = "你好！告诉我品类、预算和偏好，我来帮你推荐商品。你也可以追问「再便宜一点」或「为什么推荐第一款」。";

    /** 后端 POST /chat/stream 已就绪，默认走 SSE；404 时自动回退 POST /chat */
    private static final boolean USE_SSE_STREAM = true;

    private EditText etMessage;
    private Button btnSend;
    private Button btnNewChat;
    private ChipGroup chipGroupExamples;
    private RecyclerView rvChat;

    private ChatAdapter chatAdapter;
    private final List<ChatUiMessage> chatMessages = new ArrayList<>();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private SharedPreferences prefs;
    private String sessionId;
    private boolean isSending = false;

    private ChatSseClient chatSseClient;
    private int streamingAssistantIndex = -1;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        chatSseClient = new ChatSseClient();

        etMessage = findViewById(R.id.etMessage);
        btnSend = findViewById(R.id.btnSend);
        btnNewChat = findViewById(R.id.btnNewChat);
        chipGroupExamples = findViewById(R.id.chipGroupExamples);
        rvChat = findViewById(R.id.rvChat);

        chatAdapter = new ChatAdapter(chatMessages);
        rvChat.setLayoutManager(new LinearLayoutManager(this));
        rvChat.setAdapter(chatAdapter);

        sessionId = prefs.getString(KEY_SESSION_ID, null);
        if (sessionId == null) {
            startNewSession(false);
        } else {
            addWelcomeMessage();
        }

        btnSend.setOnClickListener(v -> sendCurrentMessage());
        btnNewChat.setOnClickListener(v -> startNewSession(true));

        etMessage.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                sendCurrentMessage();
                return true;
            }
            return false;
        });

        setupExampleChips();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        chatSseClient.cancel();
    }

    private void setupExampleChips() {
        chipGroupExamples.setOnCheckedStateChangeListener((group, checkedIds) -> {
            if (checkedIds.isEmpty()) {
                return;
            }
            Chip chip = findViewById(checkedIds.get(0));
            if (chip == null) {
                return;
            }

            String text = chip.getText().toString();
            if ("拍照手机".equals(text)) {
                etMessage.setText("预算9000以内，想买拍照好的手机");
            } else if ("抗初老精华".equals(text)) {
                etMessage.setText("敏感肌能用的抗初老精华");
            } else if ("凉快T恤".equals(text)) {
                etMessage.setText("夏天通勤穿的凉快 T 恤");
            } else if ("速溶咖啡".equals(text)) {
                etMessage.setText("新手想买精品速溶咖啡");
            }
            etMessage.setSelection(etMessage.getText().length());
            chipGroupExamples.clearCheck();
        });
    }

    private void startNewSession(boolean showToast) {
        sessionId = UUID.randomUUID().toString();
        prefs.edit().putString(KEY_SESSION_ID, sessionId).apply();
        chatSseClient.cancel();
        chatMessages.clear();
        streamingAssistantIndex = -1;
        addWelcomeMessage();
        setSendingState(false);
        if (showToast) {
            Toast.makeText(this, "已开始新对话", Toast.LENGTH_SHORT).show();
        }
    }

    private void addWelcomeMessage() {
        chatMessages.add(ChatUiMessage.assistant(WELCOME_MESSAGE));
        chatAdapter.notifyDataSetChanged();
        scrollToBottom();
    }

    private void sendCurrentMessage() {
        String message = etMessage.getText().toString().trim();
        if (message.isEmpty()) {
            Toast.makeText(this, "请输入消息", Toast.LENGTH_SHORT).show();
            return;
        }
        if (isSending) {
            return;
        }

        if (sessionId == null) {
            startNewSession(false);
        }

        etMessage.setText("");
        chatMessages.add(ChatUiMessage.user(message));
        chatMessages.add(ChatUiMessage.loading());
        chatAdapter.notifyDataSetChanged();
        scrollToBottom();

        setSendingState(true);
        if (USE_SSE_STREAM) {
            sendViaSse(message);
        } else {
            sendViaRest(message);
        }
    }

    /**
     * 优先走 SSE；后端尚未提供 /chat/stream 时自动回退 POST /chat。
     */
    private void sendViaSse(String message) {
        chatSseClient.streamChat(sessionId, message, new ChatSseClient.StreamListener() {
            @Override
            public void onTextDelta(String content) {
                mainHandler.post(() -> appendStreamingText(content));
            }

            @Override
            public void onItems(List<RecommendResponse.Item> items) {
                mainHandler.post(() -> appendProductItems(items));
            }

            @Override
            public void onDone() {
                mainHandler.post(() -> finishStreamingResponse());
            }

            @Override
            public void onError(String errorMessage) {
                mainHandler.post(() -> {
                    removeLoadingMessage();
                    chatMessages.add(ChatUiMessage.assistant(errorMessage));
                    chatAdapter.notifyDataSetChanged();
                    scrollToBottom();
                    setSendingState(false);
                });
            }

            @Override
            public void onFallbackToRest() {
                mainHandler.post(() -> sendViaRest(message));
            }
        });
    }

    private void sendViaRest(String message) {
        ChatRequest request = new ChatRequest(sessionId, message);

        RetrofitClient.getInstance()
                .getApiService()
                .chat(request)
                .enqueue(new Callback<ChatResponse>() {
                    @Override
                    public void onResponse(Call<ChatResponse> call, Response<ChatResponse> response) {
                        if (!response.isSuccessful() || response.body() == null) {
                            onFailure(call, new RuntimeException("HTTP " + response.code()));
                            return;
                        }
                        handleChatResponse(response.body());
                    }

                    @Override
                    public void onFailure(Call<ChatResponse> call, Throwable t) {
                        removeLoadingMessage();
                        chatMessages.add(ChatUiMessage.assistant("网络错误，请确认后端已启动（http://127.0.0.1:8000）"));
                        chatAdapter.notifyDataSetChanged();
                        scrollToBottom();
                        setSendingState(false);
                    }
                });
    }

    private void appendStreamingText(String delta) {
        removeLoadingMessage();

        if (streamingAssistantIndex < 0 || streamingAssistantIndex >= chatMessages.size()) {
            ChatUiMessage assistant = ChatUiMessage.assistant("");
            assistant.setStreaming(true);
            chatMessages.add(assistant);
            streamingAssistantIndex = chatMessages.size() - 1;
        }

        ChatUiMessage assistant = chatMessages.get(streamingAssistantIndex);
        assistant.appendContent(delta);
        chatAdapter.notifyItemChanged(streamingAssistantIndex);
        scrollToBottom();
    }

    private void appendProductItems(List<RecommendResponse.Item> items) {
        if (items == null || items.isEmpty()) {
            return;
        }
        List<Product> productList = new ArrayList<>();
        for (RecommendResponse.Item item : items) {
            productList.add(toProduct(item));
        }
        chatMessages.add(ChatUiMessage.productRow(productList));
        chatAdapter.notifyDataSetChanged();
        scrollToBottom();
    }

    private void finishStreamingResponse() {
        if (streamingAssistantIndex >= 0 && streamingAssistantIndex < chatMessages.size()) {
            ChatUiMessage assistant = chatMessages.get(streamingAssistantIndex);
            assistant.setStreaming(false);
            if (assistant.getContent() == null || assistant.getContent().isEmpty()) {
                assistant.setContent("已完成推荐。");
            }
            chatAdapter.notifyItemChanged(streamingAssistantIndex);
        }
        streamingAssistantIndex = -1;
        setSendingState(false);
        scrollToBottom();
    }

    private void handleChatResponse(ChatResponse response) {
        removeLoadingMessage();

        if (response.getSession_id() != null) {
            sessionId = response.getSession_id();
            prefs.edit().putString(KEY_SESSION_ID, sessionId).apply();
        }

        String reply = response.getReply();
        if (reply == null || reply.isEmpty()) {
            reply = "已完成处理。";
        }
        chatMessages.add(ChatUiMessage.assistant(reply));

        List<RecommendResponse.Item> items = response.getItems();
        if (items != null && !items.isEmpty()) {
            List<Product> productList = new ArrayList<>();
            for (RecommendResponse.Item item : items) {
                productList.add(toProduct(item));
            }
            chatMessages.add(ChatUiMessage.productRow(productList));
        }

        chatAdapter.notifyDataSetChanged();
        scrollToBottom();
        setSendingState(false);
    }

    private void removeLoadingMessage() {
        for (int i = chatMessages.size() - 1; i >= 0; i--) {
            if (chatMessages.get(i).getType() == ChatUiMessage.TYPE_LOADING) {
                chatMessages.remove(i);
                chatAdapter.notifyItemRemoved(i);
                if (streamingAssistantIndex > i) {
                    streamingAssistantIndex--;
                }
                break;
            }
        }
    }

    private Product toProduct(RecommendResponse.Item item) {
        Product product = new Product();
        product.setProduct_id(item.getProduct_id());
        product.setTitle(item.getTitle());
        product.setBrand(item.getBrand());
        product.setBase_price(item.getPrice());
        product.setReason(item.getReason());
        product.setMatched_evidence(item.getEvidence());
        product.setCategory("");
        product.setSub_category("");
        return product;
    }

    private void setSendingState(boolean sending) {
        isSending = sending;
        btnSend.setEnabled(!sending);
        btnSend.setText(sending ? "发送中" : "发送");
    }

    private void scrollToBottom() {
        if (chatMessages.isEmpty()) {
            return;
        }
        rvChat.post(() -> rvChat.smoothScrollToPosition(chatMessages.size() - 1));
    }
}
