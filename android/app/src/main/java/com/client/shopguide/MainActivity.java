package com.client.shopguide;

import android.Manifest;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.speech.tts.TextToSpeech;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.LinearLayout;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.client.shopguide.adapter.ChatAdapter;
import com.client.shopguide.model.ChatRequest;
import com.client.shopguide.model.ChatResponse;
import com.client.shopguide.model.ChatUiMessage;
import com.client.shopguide.model.CompareMock;
import com.client.shopguide.model.Product;
import com.client.shopguide.model.RecommendResponse;
import com.client.shopguide.network.ChatSseClient;
import com.client.shopguide.voice.BaiduAsrClient;
import coil.Coil;
import coil.request.ImageRequest;
import com.google.android.material.bottomsheet.BottomSheetDialog;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class MainActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "shopguide_chat";
    private static final String KEY_SESSION_ID = "session_id";
    private static final String KEY_LAST_ACTIVE = "last_active_time";
    private static final String MESSAGES_FILE = "chat_messages.json";
    private static final int SESSION_GAP_MINUTES = 5;
    private static final String WELCOME_MESSAGE = "你好！告诉我品类、预算和偏好，我来帮你推荐商品。你也可以追问「再便宜一点」或「为什么推荐第一款」。";

    /** 后端 POST /chat/stream 已就绪，默认走 SSE；404 时自动回退 POST /chat */
    private static final boolean USE_SSE_STREAM = true;

    private Gson gson;

    private EditText etMessage;
    private ImageButton btnMic;
    private ImageButton btnPlus;
    private ImageButton btnSend;
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

    // 功能面板
    private LinearLayout llFunctionPanel;
    private boolean isPanelVisible = false;

    // 语音识别
    private boolean isListening = false;

    // 购物车
    private final List<Product> cartProducts = new ArrayList<>();

    // TTS 语音
    private TextToSpeech tts;

    // SSE 状态：result_count
    private int pendingResultCount = 0;
    private int pendingItemsCount = 0;

    // 拍照相关
    private Uri currentPhotoUri;

    // ActivityResultLauncher
    /** 拍照 */
    private final ActivityResultLauncher<Uri> takePhotoLauncher =
            registerForActivityResult(new ActivityResultContracts.TakePicture(), success -> {
                if (success && currentPhotoUri != null) {
                    Toast.makeText(this, "已拍照：" + currentPhotoUri.getPath(), Toast.LENGTH_SHORT).show();
                    // TODO: 上传图片到后端接口，拿到返回结果后插入对话
                }
            });

    /** 相册选图 */
    private final ActivityResultLauncher<String> pickImageLauncher =
            registerForActivityResult(new ActivityResultContracts.GetContent(), uri -> {
                if (uri != null) {
                    Toast.makeText(this, "已选图：" + uri.getPath(), Toast.LENGTH_SHORT).show();
                    // TODO: 上传图片到后端接口，拿到返回结果后插入对话
                }
            });

    /** 权限请求 */
    private final ActivityResultLauncher<String[]> permissionLauncher =
            registerForActivityResult(new ActivityResultContracts.RequestMultiplePermissions(), permissions -> {
                boolean cameraGranted = Boolean.TRUE.equals(permissions.get(Manifest.permission.CAMERA));
                boolean storageGranted;
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
                    storageGranted = Boolean.TRUE.equals(permissions.get(Manifest.permission.READ_MEDIA_IMAGES));
                } else {
                    storageGranted = Boolean.TRUE.equals(permissions.get(Manifest.permission.READ_EXTERNAL_STORAGE));
                }
                if (cameraGranted && storageGranted) {
                    openCamera();
                } else {
                    Toast.makeText(this, "需要相机和存储权限才能使用拍照功能", Toast.LENGTH_SHORT).show();
                }
            });

    // ========== Lifecycle ==========

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        chatSseClient = new ChatSseClient();
        gson = new Gson();

        initViews();
        initRecyclerView();
        loadHistoryAndInitSession();
        setupListeners();
    }

    @Override
    protected void onStop() {
        super.onStop();
        saveMessages();
        prefs.edit().putLong(KEY_LAST_ACTIVE, System.currentTimeMillis()).apply();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        chatSseClient.cancel();
        if (tts != null) {
            tts.stop();
            tts.shutdown();
        }
    }

    // ========== 初始化 ==========

    private void initViews() {
        etMessage = findViewById(R.id.etMessage);
        btnMic = findViewById(R.id.btnMic);
        btnPlus = findViewById(R.id.btnPlus);
        btnSend = findViewById(R.id.btnSend);
        btnNewChat = findViewById(R.id.btnNewChat);
        chipGroupExamples = findViewById(R.id.chipGroupExamples);
        rvChat = findViewById(R.id.rvChat);
        llFunctionPanel = findViewById(R.id.llFunctionPanel);
    }

    private void initRecyclerView() {
        chatAdapter = new ChatAdapter(chatMessages);
        chatAdapter.setOnAddToCartListener(product -> {
            if (!cartProducts.contains(product)) {
                cartProducts.add(product);
            }
        });
        // TTS 回调
        tts = new TextToSpeech(this, status -> {});
        chatAdapter.setOnTTSListener(text -> {
            tts.setLanguage(Locale.CHINESE);
            tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, null);
        });
        rvChat.setLayoutManager(new LinearLayoutManager(this));
        rvChat.setAdapter(chatAdapter);

        // 触摸列表 → 隐藏 TTS 图标
        rvChat.setOnTouchListener((v, event) -> {
            if (event.getAction() == android.view.MotionEvent.ACTION_DOWN) {
                chatAdapter.dismissTts();
            }
            return false;
        });
    }

    private void initSession() {
        sessionId = prefs.getString(KEY_SESSION_ID, null);
        if (sessionId == null) {
            startNewSession(false);
        } else {
            addWelcomeMessage();
        }
    }

    private void setupListeners() {
        // 回车发送
        etMessage.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                sendCurrentMessage();
                return true;
            }
            return false;
        });

        // 新对话
        btnNewChat.setOnClickListener(v -> startNewSession(true));

        // 发送按钮
        btnSend.setOnClickListener(v -> sendCurrentMessage());

        // 麦克风按钮 → 语音识别
        btnMic.setOnClickListener(v -> startVoiceInput());

        // 加号按钮 → 展开/收起内嵌功能面板
        btnPlus.setOnClickListener(v -> toggleFunctionPanel());

        setupExampleChips();
        setupFunctionPanel();
    }

    // ========== 百度语音识别 ==========

    private void startVoiceInput() {
        if (isListening) return;
        if (isSending) return;

        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 100);
            return;
        }

        isListening = true;
        Toast.makeText(this, "正在聆听...", Toast.LENGTH_SHORT).show();

        // 后台线程执行录音 + 百度识别
        new Thread(() -> {
            String result = null;
            boolean hasVoice = true;
            try {
                result = recordAndRecognize();
            } catch (Exception e) {
                e.printStackTrace();
                hasVoice = false;
            }
            String finalResult = result;
            boolean finalHasVoice = hasVoice;

            mainHandler.post(() -> {
                isListening = false;
                if (finalResult != null && !finalResult.isEmpty()) {
                    etMessage.setText(finalResult);
                    etMessage.setSelection(finalResult.length());
                } else if (!finalHasVoice) {
                    Toast.makeText(this, "未检测到说话声，请重试", Toast.LENGTH_SHORT).show();
                } else {
                    Toast.makeText(this, "未识别到语音，请重试", Toast.LENGTH_SHORT).show();
                }
            });
        }).start();
    }

    /**
     * 录音（16kHz PCM）+ VAD 检测 → 百度 ASR 接口识别
     * 只有检测到人声才提交识别，静音/噪音直接跳过
     */
    private String recordAndRecognize() throws Exception {
        int sampleRate = 16000;
        int bufferSize = AudioRecord.getMinBufferSize(sampleRate,
                AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);

        AudioRecord audioRecord = new AudioRecord(MediaRecorder.AudioSource.MIC,
                sampleRate, AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT, bufferSize * 2);

        audioRecord.startRecording();

        java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
        byte[] buffer = new byte[bufferSize];
        long startTime = System.currentTimeMillis();

        // VAD 统计：统计有多少帧有声音能量
        int totalFrames = 0;
        int voiceFrames = 0;
        final int VAD_THRESHOLD = 250; // RMS 阈值，低于此值视为静音/噪音

        // 录制最长 3 秒，同时做 VAD 检测
        while (System.currentTimeMillis() - startTime < 3000) {
            int read = audioRecord.read(buffer, 0, buffer.length);
            if (read > 0) {
                baos.write(buffer, 0, read);
                totalFrames++;
                if (calcRms(buffer, read) > VAD_THRESHOLD) {
                    voiceFrames++;
                }
            }
        }

        audioRecord.stop();
        audioRecord.release();

        // 超过 80% 的帧静音才判定无有效语音
        if (totalFrames == 0 || voiceFrames < totalFrames * 0.2) {
            throw new Exception("VAD_SILENCE"); // 未检测到说话声
        }

        byte[] pcmData = baos.toByteArray();
        if (pcmData.length == 0) return null;

        return BaiduAsrClient.recognize(pcmData, pcmData.length);
    }

    /** 计算 PCM 16bit 数据的 RMS（均方根能量） */
    private double calcRms(byte[] data, int length) {
        long sum = 0;
        int samples = length / 2;
        for (int i = 0; i < length - 1; i += 2) {
            // 小端序：低字节 + 高字节
            short sample = (short) ((data[i] & 0xFF) | (data[i + 1] << 8));
            sum += sample * sample;
        }
        return samples > 0 ? Math.sqrt((double) sum / samples) : 0;
    }

    // ========== 功能面板（微信式滑入/滑出） ==========

    private void toggleFunctionPanel() {
        if (isPanelVisible) {
            hideFunctionPanel();
        } else {
            showFunctionPanel();
        }
    }

    private void showFunctionPanel() {
        if (isPanelVisible) return;
        isPanelVisible = true;
        llFunctionPanel.setVisibility(View.VISIBLE);
        scrollToBottom();
    }

    private void hideFunctionPanel() {
        if (!isPanelVisible) return;
        isPanelVisible = false;
        llFunctionPanel.setVisibility(View.GONE);
    }

    private void setupFunctionPanel() {
        // 相册
        LinearLayout llAlbum = findViewById(R.id.llAlbum);
        llAlbum.setOnClickListener(v -> {
            openGallery();
            hideFunctionPanel();
        });

        // 拍照
        LinearLayout llCamera = findViewById(R.id.llCamera);
        llCamera.setOnClickListener(v -> {
            requestCameraPermission();
            hideFunctionPanel();
        });

        // 购物车 → 商品多选 BottomSheet
        LinearLayout llCart = findViewById(R.id.llCart);
        llCart.setOnClickListener(v -> {
            hideFunctionPanel();
            showShoppingCart();
        });

    }

    // 拍照

    private void requestCameraPermission() {
        List<String> neededPermissions = new ArrayList<>();

        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            neededPermissions.add(Manifest.permission.CAMERA);
        }

        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(Manifest.permission.READ_MEDIA_IMAGES) != PackageManager.PERMISSION_GRANTED) {
                neededPermissions.add(Manifest.permission.READ_MEDIA_IMAGES);
            }
        } else {
            if (checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
                neededPermissions.add(Manifest.permission.READ_EXTERNAL_STORAGE);
            }
        }

        if (neededPermissions.isEmpty()) {
            openCamera();
        } else {
            permissionLauncher.launch(neededPermissions.toArray(new String[0]));
        }
    }

    private void openCamera() {
        Intent takePictureIntent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        if (takePictureIntent.resolveActivity(getPackageManager()) != null) {
            File photoFile = null;
            try {
                photoFile = createImageFile();
            } catch (IOException e) {
                Toast.makeText(this, "创建图片文件失败", Toast.LENGTH_SHORT).show();
                return;
            }

            if (photoFile != null) {
                currentPhotoUri = FileProvider.getUriForFile(this,
                        getPackageName() + ".fileprovider", photoFile);
                takePictureIntent.putExtra(MediaStore.EXTRA_OUTPUT, currentPhotoUri);
                takePhotoLauncher.launch(currentPhotoUri);
            }
        } else {
            Toast.makeText(this, "设备不支持拍照", Toast.LENGTH_SHORT).show();
        }
    }

    private File createImageFile() throws IOException {
        String timeStamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(new Date());
        String imageFileName = "JPEG_" + timeStamp + "_";
        File storageDir = getExternalFilesDir(Environment.DIRECTORY_PICTURES);
        return File.createTempFile(imageFileName, ".jpg", storageDir);
    }

    // 相册

    private void openGallery() {
        pickImageLauncher.launch("image/*");
    }

    // 示例 Chip

    private void setupExampleChips() {
        chipGroupExamples.setOnCheckedStateChangeListener((group, checkedIds) -> {
            if (checkedIds.isEmpty()) return;
            Chip chip = findViewById(checkedIds.get(0));
            if (chip == null) return;
            String text = chip.getText().toString();
            if ("拍照手机求推荐".equals(text)) {
                etMessage.setText("预算9000以内，想买拍照好的手机");
            } else if ("有没有好用的抗初老精华".equals(text)) {
                etMessage.setText("敏感肌能用的抗初老精华");
            } else if ("要是有凉快T恤就好了".equals(text)) {
                etMessage.setText("夏天通勤穿的凉快 T 恤");
            } else if ("想喝速溶咖啡急急急".equals(text)) {
                etMessage.setText("新手想买精品速溶咖啡");
            }
            etMessage.setSelection(etMessage.getText().length());
            chipGroupExamples.clearCheck();
        });
    }

    // 会话管理

    private void startNewSession(boolean showToast) {
        saveMessages();
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

    // ========== 历史记录存取 ==========

    private void loadHistoryAndInitSession() {
        long lastActive = prefs.getLong(KEY_LAST_ACTIVE, 0);
        long now = System.currentTimeMillis();
        boolean isNewSession = (lastActive == 0) || (now - lastActive > SESSION_GAP_MINUTES * 60_000L);

        // 从文件加载旧消息
        List<ChatUiMessage> storedMessages = loadMessagesFromFile();
        if (storedMessages != null && !storedMessages.isEmpty()) {
            chatMessages.addAll(storedMessages);
            if (isNewSession) {
                // 插入时间分割线
                SimpleDateFormat sdf = new SimpleDateFormat("MM-dd HH:mm", Locale.getDefault());
                chatMessages.add(ChatUiMessage.divider(sdf.format(new Date(lastActive))));
                // 新 session
                sessionId = UUID.randomUUID().toString();
                prefs.edit().putString(KEY_SESSION_ID, sessionId).apply();
                addWelcomeMessage();
            } else {
                // 30分钟内回来，恢复上次 session
                sessionId = prefs.getString(KEY_SESSION_ID, null);
                if (sessionId == null) {
                    sessionId = UUID.randomUUID().toString();
                    prefs.edit().putString(KEY_SESSION_ID, sessionId).apply();
                    addWelcomeMessage();
                }
            }
            chatAdapter.notifyDataSetChanged();
            scrollToBottom();
            return;
        }

        // 没有历史：全新开始
        sessionId = UUID.randomUUID().toString();
        prefs.edit().putString(KEY_SESSION_ID, sessionId).apply();
        addWelcomeMessage();
    }

    private void saveMessages() {
        // 过滤掉 loading 和 divider 类型，只保存用户/AI/商品/对比
        List<ChatUiMessage> toSave = new ArrayList<>();
        for (ChatUiMessage msg : chatMessages) {
            if (msg.getType() != ChatUiMessage.TYPE_LOADING
                    && msg.getType() != ChatUiMessage.TYPE_DIVIDER) {
                toSave.add(msg);
            }
        }
        if (toSave.isEmpty()) return;

        try {
            File file = new File(getFilesDir(), MESSAGES_FILE);
            OutputStreamWriter writer = new OutputStreamWriter(new FileOutputStream(file), "UTF-8");
            gson.toJson(toSave, writer);
            writer.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private List<ChatUiMessage> loadMessagesFromFile() {
        try {
            File file = new File(getFilesDir(), MESSAGES_FILE);
            if (!file.exists()) return null;
            InputStreamReader reader = new InputStreamReader(new FileInputStream(file), "UTF-8");
            List<ChatUiMessage> loaded = gson.fromJson(reader,
                    new TypeToken<List<ChatUiMessage>>() {}.getType());
            reader.close();
            return loaded;
        } catch (IOException e) {
            e.printStackTrace();
            return null;
        }
    }

    // ========== 发送消息 ==========

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

        // 检测"对比"关键词 → 插入 Mock 对比卡片
        // TODO: 等后端 /compare 接口 ready 后，替换为真实 API 调用
        if (message.contains("对比")) {
            chatMessages.add(ChatUiMessage.compare(CompareMock.getMockData()));
        }

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
        pendingResultCount = 0;
        pendingItemsCount = 0;
        chatSseClient.streamChat(sessionId, message, new ChatSseClient.StreamListener() {
            @Override
            public void onTextDelta(String content) {
                mainHandler.post(() -> appendStreamingText(content));
            }

            @Override
            public void onState(int resultCount) {
                mainHandler.post(() -> pendingResultCount = resultCount);
            }

            @Override
            public void onItems(List<RecommendResponse.Item> items) {
                mainHandler.post(() -> {
                    appendProductItems(items);
                    pendingItemsCount = items != null ? items.size() : 0;
                });
            }

            @Override
            public void onDone() {
                mainHandler.post(() -> {
                    finishStreamingResponse();
                    showResultCount();
                });
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
                    public void onResponse(@NonNull Call<ChatResponse> call, @NonNull Response<ChatResponse> response) {
                        if (!response.isSuccessful() || response.body() == null) {
                            onFailure(call, new RuntimeException("HTTP " + response.code()));
                            return;
                        }
                        handleChatResponse(response.body());
                    }

                    @Override
                    public void onFailure(@NonNull Call<ChatResponse> call, @NonNull Throwable t) {
                        removeLoadingMessage();
                        chatMessages.add(ChatUiMessage.assistant("网络错误，请确认后端已启动（http://127.0.0.1:8000）"));
                        chatAdapter.notifyDataSetChanged();
                        scrollToBottom();
                        setSendingState(false);
                    }
                });
    }

    // ========== SSE 流式处理 ==========

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

    // ========== REST 响应处理 ==========

    private void handleChatResponse(ChatResponse response) {
        removeLoadingMessage();

        pendingResultCount = response.getResult_count();

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
        pendingItemsCount = items != null ? items.size() : 0;
        if (items != null && !items.isEmpty()) {
            List<Product> productList = new ArrayList<>();
            for (RecommendResponse.Item item : items) {
                productList.add(toProduct(item));
            }
            chatMessages.add(ChatUiMessage.productRow(productList));
        }

        chatAdapter.notifyDataSetChanged();
        scrollToBottom();
        showResultCount();
        setSendingState(false);
    }

    // ========== 工具方法 ==========

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
        product.setImageUrl(item.getImage_url());
        product.setPriceRange(item.getPrice_range());
        product.setRating(item.getRating());
        product.setSoldCount(item.getSold_count());
        product.setReviewCount(item.getReview_count());
        product.setMarketingDesc(item.getMarketing_desc());
        product.setReviews(item.getReviews());
        product.setFaqs(item.getFaqs());
        return product;
    }

    private void showResultCount() {
        if (pendingResultCount > pendingItemsCount && pendingItemsCount > 0) {
            chatMessages.add(ChatUiMessage.divider(
                    "共找到 " + pendingResultCount + " 件，已为你推荐 " + pendingItemsCount + " 款"));
            chatAdapter.notifyItemInserted(chatMessages.size() - 1);
            scrollToBottom();
        }
    }

    private void setSendingState(boolean sending) {
        isSending = sending;
        etMessage.setEnabled(!sending);
        btnSend.setEnabled(!sending);
    }

    private void scrollToBottom() {
        if (chatMessages.isEmpty()) {
            return;
        }
        rvChat.post(() -> rvChat.smoothScrollToPosition(chatMessages.size() - 1));
    }

    // ========== 购物车多选面板 ==========

    private void showShoppingCart() {
        BottomSheetDialog sheet = new BottomSheetDialog(this);
        View sheetView = LayoutInflater.from(this).inflate(R.layout.bottom_sheet_shopping_cart, null);
        sheet.setContentView(sheetView);

        RecyclerView rv = sheetView.findViewById(R.id.rvCartProducts);
        rv.setLayoutManager(new androidx.recyclerview.widget.GridLayoutManager(this, 2));

        if (cartProducts.isEmpty()) {
            Toast.makeText(this, "购物车为空，请先添加商品", Toast.LENGTH_SHORT).show();
            return;
        }

        CartProductAdapter cartAdapter = new CartProductAdapter(cartProducts);
        rv.setAdapter(cartAdapter);

        sheetView.findViewById(R.id.btnCartConfirm).setOnClickListener(v -> {
            List<String> selected = cartAdapter.getSelectedNames();
            if (selected.isEmpty()) {
                Toast.makeText(this, "请至少选一个商品", Toast.LENGTH_SHORT).show();
                return;
            }
            StringBuilder sb = new StringBuilder();
            for (String name : selected) {
                if (sb.length() > 0) sb.append("、");
                sb.append(name);
            }
            etMessage.setText("帮我看看 " + sb);
            etMessage.setSelection(etMessage.length());
            sheet.dismiss();
        });

        sheet.show();
    }

    static class CartProductAdapter extends RecyclerView.Adapter<CartProductAdapter.Vh> {
        private static final String IMG_BASE = "http://10.0.2.2:8000";
        private final List<Product> items;
        private final boolean[] selected;

        CartProductAdapter(List<Product> items) {
            this.items = items;
            this.selected = new boolean[items.size()];
        }

        List<String> getSelectedNames() {
            List<String> names = new ArrayList<>();
            for (int i = 0; i < items.size(); i++) {
                if (selected[i]) names.add(items.get(i).getTitle());
            }
            return names;
        }

        @NonNull @Override
        public Vh onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext())
                    .inflate(R.layout.item_shopping_cart_product, parent, false);
            return new Vh(v);
        }

        @Override
        public void onBindViewHolder(@NonNull Vh h, int pos) {
            Product p = items.get(pos);
            h.tvName.setText(p.getTitle());
            h.tvPrice.setText(String.format("¥%.0f", p.getBase_price()));
            h.cbSelect.setChecked(selected[pos]);
            h.cbSelect.setOnCheckedChangeListener((btn, checked) -> selected[pos] = checked);

            String url = p.getImageUrl();
            if (url != null && !url.isEmpty()) {
                ImageRequest req = new ImageRequest.Builder(h.itemView.getContext())
                        .data(IMG_BASE + url)
                        .target(h.ivImage)
                        .placeholder(R.drawable.ic_placeholder_product)
                        .error(R.drawable.ic_placeholder_product)
                        .crossfade(200)
                        .build();
                Coil.imageLoader(h.itemView.getContext()).enqueue(req);
            }
        }

        @Override public int getItemCount() { return items.size(); }

        static class Vh extends RecyclerView.ViewHolder {
            CheckBox cbSelect;
            TextView tvName, tvPrice;
            ImageView ivImage;
            Vh(@NonNull View v) {
                super(v);
                cbSelect = v.findViewById(R.id.cbSelect);
                tvName = v.findViewById(R.id.tvCartName);
                tvPrice = v.findViewById(R.id.tvCartPrice);
                ivImage = v.findViewById(R.id.ivCartImage);
            }
        }
    }
}
