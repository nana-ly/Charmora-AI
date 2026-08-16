package com.client.shopguide;

import android.Manifest;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaPlayer;
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
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.client.shopguide.adapter.ChatAdapter;
import com.client.shopguide.model.ChatRequest;
import com.client.shopguide.model.ChatResponse;
import com.client.shopguide.model.ChatUiMessage;
import com.client.shopguide.model.Product;
import com.client.shopguide.model.RecommendResponse;
import com.client.shopguide.network.BackendApiClient;
import com.client.shopguide.network.ChatSseClient;
import coil.Coil;
import coil.request.ImageRequest;
import com.google.android.material.bottomsheet.BottomSheetDialog;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.Map;
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
    private static final String WELCOME_MESSAGE = "你好，想买点什么？\n告诉我想买的品类、预算和偏好的话，我能更懂你。";

    /** 后端 POST /chat/stream 已就绪，默认走 SSE；404 时自动回退 POST /chat */
    private static final boolean USE_SSE_STREAM = true;

    private Gson gson;

    private EditText etMessage;
    private ImageButton btnMic;
    private ImageButton btnSend;
    private ImageButton btnPlus;
    private ImageButton btnNewChat;
    private ImageButton btnMenu;
    private ChipGroup chipGroupExamples;
    private RecyclerView rvChat;
    private RecyclerView rvHistory;
    private EditText etHistorySearch;
    private LinearLayout drawerHistoryPanel;

    private androidx.drawerlayout.widget.DrawerLayout drawerLayout;

    private ChatAdapter chatAdapter;
    private final List<ChatUiMessage> chatMessages = new ArrayList<>();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private SharedPreferences prefs;
    private String sessionId;
    private boolean isSending = false;

    private ChatSseClient chatSseClient;
    private BackendApiClient backendApiClient;
    private int streamingAssistantIndex = -1;

    // 流式文本逐字输出：缓冲区 + 定时排空
    private final StringBuilder streamingBuffer = new StringBuilder();
    private boolean flushScheduled = false;
    private boolean streamFinished = false;
    private static final long FLUSH_INTERVAL_MS = 45;
    private static final int FLUSH_CHARS_PER_TICK = 5;
    private final Runnable flushTask = new Runnable() {
        @Override
        public void run() {
            if (streamingBuffer.length() == 0) {
                flushScheduled = false;
                if (streamFinished) {
                    finishStreamingResponse();
                    showResultCount();
                }
                return;
            }
            if (streamingAssistantIndex < 0 || streamingAssistantIndex >= chatMessages.size()) {
                streamingBuffer.setLength(0);
                flushScheduled = false;
                return;
            }
            int take = Math.min(FLUSH_CHARS_PER_TICK, streamingBuffer.length());
            String chunk = streamingBuffer.substring(0, take);
            streamingBuffer.delete(0, take);

            ChatUiMessage assistant = chatMessages.get(streamingAssistantIndex);
            assistant.appendContent(chunk);
            chatAdapter.notifyItemChanged(streamingAssistantIndex);
            scrollToBottom();

            if (streamingBuffer.length() > 0) {
                mainHandler.postDelayed(this, FLUSH_INTERVAL_MS);
            } else {
                flushScheduled = false;
                if (streamFinished) {
                    finishStreamingResponse();
                    showResultCount();
                }
            }
        }
    };

    // 商品/对比卡片逐条输出
    private boolean itemFlushScheduled = false;
    private static final long ITEM_FLUSH_INTERVAL_MS = 400;
    private final List<Product> streamingProductList = new ArrayList<>();
    private final Runnable itemFlushTask = new Runnable() {
        @Override
        public void run() {
            if (pendingStreamItems == null || pendingStreamItems.isEmpty()) {
                itemFlushScheduled = false;
                return;
            }
            RecommendResponse.Item raw = pendingStreamItems.remove(0);
            displaySingleItem(raw);

            if (!pendingStreamItems.isEmpty()) {
                mainHandler.postDelayed(this, ITEM_FLUSH_INTERVAL_MS);
            } else {
                itemFlushScheduled = false;
                pendingStreamItems = null;
                // 推荐模式累积完毕后一次性创建 PRODUCT_ROW
                flushStreamingProductRow();
            }
        }
    };

    /**
     * 展示单个商品 item。
     * 对比模式：每条创建独立 COMPARE_PRODUCT 气泡，逐条插入。
     * 推荐模式：先累积到 streamingProductList，待全部排空后由 flushStreamingProductRow 统一展示。
     */
    private void displaySingleItem(RecommendResponse.Item raw) {
        Product product = toProduct(raw);
        if (isCurrentAction("compare")) {
            int idx = 1;
            for (ChatUiMessage m : chatMessages) {
                if (m.getType() == ChatUiMessage.TYPE_COMPARE_PRODUCT) idx++;
            }
            chatMessages.add(ChatUiMessage.compareProduct(product, idx));
            chatAdapter.notifyItemInserted(chatMessages.size() - 1);
            scrollToBottom();
        } else {
            streamingProductList.add(product);
        }
    }

    /** 推荐模式：将累积的商品一次性创建 PRODUCT_ROW（横向滚屏）。 */
    private void flushStreamingProductRow() {
        if (streamingProductList.isEmpty()) return;
        chatMessages.add(ChatUiMessage.productRow(new ArrayList<>(streamingProductList)));
        chatAdapter.notifyItemInserted(chatMessages.size() - 1);
        streamingProductList.clear();
        scrollToBottom();
    }

    // 功能面板
    private LinearLayout llFunctionPanel;
    private boolean isPanelVisible = false;

    // 语音识别
    private boolean isListening = false;

    // 购物车
    private final List<Product> cartProducts = new ArrayList<>();

    // TTS 语音
    private TextToSpeech tts;
    private MediaPlayer mediaPlayer;

    // SSE 状态：result_count
    private int pendingResultCount = 0;
    private int pendingItemsCount = 0;
    /** SSE 完整 state（含 action/intent/result_count 等），用于判断是否展示推荐统计等 UI */
    private Map<String, Object> pendingState;
    /** SSE items 缓冲区：等 state 事件到达后决定展示推荐横滚或对比商品气泡 */
    private List<RecommendResponse.Item> pendingStreamItems;

    /** 当前思考链消息对象引用（避免索引在列表变动后失效） */
    private ChatUiMessage currentThinkingMessage;
    /** 第一次 thinking 事件已创建思考链，后续 delta 需等一帧 */
    private boolean thinkingJustCreated;

    // 拍照相关
    private Uri currentPhotoUri;

    // ActivityResultLauncher
    /** 拍照 */
    private final ActivityResultLauncher<Uri> takePhotoLauncher =
            registerForActivityResult(new ActivityResultContracts.TakePicture(), success -> {
                if (success && currentPhotoUri != null) {
                    handleSelectedImage(currentPhotoUri);
                }
            });

    /** 相册选图 */
    private final ActivityResultLauncher<String> pickImageLauncher =
            registerForActivityResult(new ActivityResultContracts.GetContent(), uri -> {
                if (uri != null) {
                    handleSelectedImage(uri);
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
        RetrofitClient.configure(this);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        chatSseClient = new ChatSseClient();
        backendApiClient = new BackendApiClient();
        gson = new Gson();

        initViews();
        initRecyclerView();
        loadHistoryAndInitSession();
        setupListeners();
        setupUnifiedBottomNavigation();
    }

    private void setupUnifiedBottomNavigation() {
        com.google.android.material.bottomnavigation.BottomNavigationView nav = findViewById(R.id.chatBottomNav);
        nav.setSelectedItemId(R.id.nav_ai);
        nav.setOnItemSelectedListener(item -> {
            if (item.getItemId() == R.id.nav_ai) return true;
            Intent intent = new Intent(this, StorefrontActivity.class);
            intent.putExtra("selected_tab", item.getItemId());
            intent.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
            startActivity(intent);
            overridePendingTransition(0, 0);
            return true;
        });
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
        mainHandler.removeCallbacks(flushTask);
        mainHandler.removeCallbacks(itemFlushTask);
        if (tts != null) {
            tts.stop();
            tts.shutdown();
        }
        if (mediaPlayer != null) {
            mediaPlayer.release();
            mediaPlayer = null;
        }
    }

    // ========== 初始化 ==========

    private void initViews() {
        etMessage = findViewById(R.id.etMessage);
        btnMic = findViewById(R.id.btnMic);
        btnSend = findViewById(R.id.btnSend);
        btnPlus = findViewById(R.id.btnPlus);
        btnNewChat = findViewById(R.id.btnNewChat);
        btnMenu = findViewById(R.id.btnMenu);
        chipGroupExamples = findViewById(R.id.chipGroupExamples);
        rvChat = findViewById(R.id.rvChat);
        rvHistory = findViewById(R.id.rvHistory);
        etHistorySearch = findViewById(R.id.etHistorySearch);
        drawerHistoryPanel = findViewById(R.id.drawerHistory);
        drawerLayout = findViewById(R.id.drawerLayout);
        // 清空历史记录
        findViewById(R.id.tvClearHistory).setOnClickListener(v -> {
            clearHistoryFiles();
            drawerLayout.closeDrawer(drawerHistoryPanel);
        });
        // 设置 → 添加商品
        findViewById(R.id.tvSettings).setOnClickListener(v -> {
            drawerLayout.closeDrawer(drawerHistoryPanel);
            showAddProductDialog();
        });
        llFunctionPanel = findViewById(R.id.llFunctionPanel);
    }

    private void initRecyclerView() {
        chatAdapter = new ChatAdapter(chatMessages);
        chatAdapter.setOnAddToCartListener(product -> {
            if (!cartProducts.contains(product)) {
                cartProducts.add(product);
            }
            addProductToServerCart(product);
        });
        // TTS 回调
        tts = new TextToSpeech(this, status -> {});
        chatAdapter.setOnTTSListener(this::speakText);
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

        // 侧边栏历史
        btnMenu.setOnClickListener(v -> {
            if (drawerLayout.isDrawerOpen(drawerHistoryPanel)) {
                drawerLayout.closeDrawer(drawerHistoryPanel);
            } else {
                loadHistoryDrawer();
                drawerLayout.openDrawer(drawerHistoryPanel);
            }
        });

        // 发送按钮
        btnSend.setOnClickListener(v -> sendCurrentMessage());

        // 麦克风按钮 → 语音识别
        btnMic.setOnClickListener(v -> startVoiceInput());

        // 加号按钮 → 展开/收起功能面板
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

        return backendApiClient.transcribePcm(pcmData);
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

    // ========== 历史抽屉 ==========

    private static final String SESSIONS_DIR = "chat_sessions";

    private void loadHistoryDrawer() {
        try {
        File dir = new File(getFilesDir(), SESSIONS_DIR);
        if (!dir.exists()) dir.mkdirs();
        File[] files = dir.listFiles();
        final List<File> sessionFiles = new ArrayList<>();
        final List<String> titles = new ArrayList<>();

        if (files != null) {
            for (File f : files) {
                if (f.getName().endsWith(".json")) {
                    sessionFiles.add(f);
                    titles.add(readSessionTitle(f));
                }
            }
        }
        if (sessionFiles.isEmpty()) {
            titles.add("暂无历史");
            sessionFiles.add(null);
        }

        rvHistory.setLayoutManager(new LinearLayoutManager(this));
        rvHistory.setAdapter(new RecyclerView.Adapter() {
            @NonNull @Override
            public RecyclerView.ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int t) {
                View card = LayoutInflater.from(parent.getContext())
                        .inflate(R.layout.item_history_session, parent, false);
                return new RecyclerView.ViewHolder(card) {};
            }
            @Override public void onBindViewHolder(@NonNull RecyclerView.ViewHolder h, int pos) {
                ((TextView) h.itemView.findViewById(R.id.tvHistoryTitle)).setText(titles.get(pos));
                File f = sessionFiles.get(pos);
                String time = f != null ? formatSessionTime(f.getName()) : "";
                ((TextView) h.itemView.findViewById(R.id.tvHistoryTime)).setText(time);
                h.itemView.setOnClickListener(v -> {
                    if (f != null) {
                        saveCurrentSessionToFile(f);
                        restoreSessionFromFile(f);
                        drawerLayout.closeDrawer(drawerHistoryPanel);
                    }
                });
            }
            @Override public int getItemCount() { return titles.size(); }
        });

        // 搜索过滤
        etHistorySearch.addTextChangedListener(new android.text.TextWatcher() {
            @Override public void afterTextChanged(android.text.Editable s) {
                String q = s.toString().trim().toLowerCase();
                titles.clear(); sessionFiles.clear();
                if (files != null) {
                    for (File f : files) {
                        if (!f.getName().endsWith(".json")) continue;
                        String t = readSessionTitle(f);
                        if (q.isEmpty() || t.toLowerCase().contains(q)) {
                            titles.add(t);
                            sessionFiles.add(f);
                        }
                    }
                }
                rvHistory.getAdapter().notifyDataSetChanged();
            }
            @Override public void beforeTextChanged(CharSequence c, int a, int b, int d) {}
            @Override public void onTextChanged(CharSequence c, int a, int b, int d) {}
        });
        } catch (Exception e) { e.printStackTrace(); }
    }

    private String readSessionTitle(File file) {
        try {
            InputStreamReader r = new InputStreamReader(new FileInputStream(file), "UTF-8");
            List<ChatUiMessage> msgs = gson.fromJson(r,
                    new TypeToken<List<ChatUiMessage>>() {}.getType());
            r.close();
            if (msgs != null) {
                for (ChatUiMessage m : msgs) {
                    if (m.getType() == ChatUiMessage.TYPE_USER && m.getContent() != null)
                        return m.getContent().length() > 30
                                ? m.getContent().substring(0, 30) + "..." : m.getContent();
                }
            }
        } catch (Exception ignored) {}
        return "对话记录";
    }

    private String formatSessionTime(String fileName) {
        try {
            long ts = Long.parseLong(fileName.replace(".json", ""));
            return new SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(new Date(ts));
        } catch (Exception ignored) {}
        return "";
    }

    private void archiveCurrentSession() {
        List<ChatUiMessage> toSave = new ArrayList<>();
        for (ChatUiMessage m : chatMessages) {
            if (m.getType() == ChatUiMessage.TYPE_LOADING
                    || m.getType() == ChatUiMessage.TYPE_DIVIDER) continue;
            if (m.getType() == ChatUiMessage.TYPE_ASSISTANT
                    && WELCOME_MESSAGE.equals(m.getContent())) continue;
            toSave.add(m);
        }
        if (toSave.isEmpty()) return;
        try {
            File dir = new File(getFilesDir(), SESSIONS_DIR);
            dir.mkdirs();
            File f = new File(dir, System.currentTimeMillis() + ".json");
            OutputStreamWriter w = new OutputStreamWriter(new FileOutputStream(f), "UTF-8");
            gson.toJson(toSave, w);
            w.close();
        } catch (IOException ignored) {}
    }

    private void saveCurrentSessionToFile(File target) {
        List<ChatUiMessage> toSave = new ArrayList<>();
        for (ChatUiMessage m : chatMessages) {
            if (m.getType() == ChatUiMessage.TYPE_LOADING
                    || m.getType() == ChatUiMessage.TYPE_DIVIDER) continue;
            toSave.add(m);
        }
        try {
            OutputStreamWriter w = new OutputStreamWriter(new FileOutputStream(target), "UTF-8");
            gson.toJson(toSave, w);
            w.close();
        } catch (IOException ignored) {}
    }

    private void restoreSessionFromFile(File file) {
        try {
            InputStreamReader r = new InputStreamReader(new FileInputStream(file), "UTF-8");
            List<ChatUiMessage> msgs = gson.fromJson(r,
                    new TypeToken<List<ChatUiMessage>>() {}.getType());
            r.close();
            if (msgs != null) {
                chatMessages.clear();
                chatMessages.addAll(msgs);
                chatAdapter.notifyDataSetChanged();
                sessionId = UUID.randomUUID().toString();
                prefs.edit().putString(KEY_SESSION_ID, sessionId).apply();
                scrollToBottom();
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void clearHistoryFiles() {
        File dir = new File(getFilesDir(), SESSIONS_DIR);
        File[] files = dir.listFiles();
        if (files != null) {
            for (File f : files) f.delete();
        }
        new File(getFilesDir(), MESSAGES_FILE).delete();
        archiveCurrentSession();
        chatMessages.clear();
        chatAdapter.notifyDataSetChanged();
        startNewSession(false);
        Toast.makeText(this, "已清空历史记录", Toast.LENGTH_SHORT).show();
    }

    private void showAddProductDialog() {
        AlertDialog dialog = new AlertDialog.Builder(this).create();
        View form = LayoutInflater.from(this).inflate(R.layout.dialog_add_product, null);
        dialog.setView(form);
        form.findViewById(R.id.btnSubmitProduct).setOnClickListener(v -> {
            Toast.makeText(this, "功能开发中，敬请期待", Toast.LENGTH_SHORT).show();
            dialog.dismiss();
        });
        dialog.show();
    }

    // ========== 功能面板切换 ==========

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
        LinearLayout llAlbum = findViewById(R.id.llAlbum);
        llAlbum.setOnClickListener(v -> { openGallery(); hideFunctionPanel(); });
        LinearLayout llCamera = findViewById(R.id.llCamera);
        llCamera.setOnClickListener(v -> { requestCameraPermission(); hideFunctionPanel(); });
        LinearLayout llCart = findViewById(R.id.llCart);
        llCart.setOnClickListener(v -> { hideFunctionPanel(); showShoppingCart(); });
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
        archiveCurrentSession();
        sessionId = UUID.randomUUID().toString();
        prefs.edit().putString(KEY_SESSION_ID, sessionId).apply();
        chatSseClient.cancel();
        mainHandler.removeCallbacks(itemFlushTask);
        drainStreamingBuffer();
        streamFinished = false;
        itemFlushScheduled = false;
        streamingProductList.clear();
        chatMessages.clear();
        streamingAssistantIndex = -1;
        pendingState = null;
        pendingStreamItems = null;
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
        // 从文件加载旧消息
        List<ChatUiMessage> storedMessages = loadMessagesFromFile();
        if (storedMessages != null && !storedMessages.isEmpty()) {
            // 过滤旧欢迎语、loading、divider
            List<ChatUiMessage> filtered = new ArrayList<>();
            for (ChatUiMessage msg : storedMessages) {
                if (msg.getType() == ChatUiMessage.TYPE_LOADING
                        || msg.getType() == ChatUiMessage.TYPE_DIVIDER) continue;
                if (msg.getType() == ChatUiMessage.TYPE_ASSISTANT
                        && WELCOME_MESSAGE.equals(msg.getContent())) continue;
                filtered.add(msg);
            }
            chatMessages.addAll(filtered);

            // 插入时间分割线
            long lastActive = prefs.getLong(KEY_LAST_ACTIVE, System.currentTimeMillis());
            SimpleDateFormat sdf = new SimpleDateFormat("MM-dd HH:mm", Locale.getDefault());
            chatMessages.add(ChatUiMessage.divider(sdf.format(new Date(lastActive))));

            // 每次打开都是新对话
            sessionId = UUID.randomUUID().toString();
            prefs.edit().putString(KEY_SESSION_ID, sessionId).apply();
            addWelcomeMessage();
            chatAdapter.notifyDataSetChanged();
            scrollToBottom();
            return;
        }

        // 第一次：全新开始
        sessionId = UUID.randomUUID().toString();
        prefs.edit().putString(KEY_SESSION_ID, sessionId).apply();
        addWelcomeMessage();
    }

    private void saveMessages() {
        // 过滤掉 loading、divider 和欢迎语，只保存用户/AI/商品
        List<ChatUiMessage> toSave = new ArrayList<>();
        for (ChatUiMessage msg : chatMessages) {
            if (msg.getType() == ChatUiMessage.TYPE_LOADING
                    || msg.getType() == ChatUiMessage.TYPE_DIVIDER) {
                continue;
            }
            if (msg.getType() == ChatUiMessage.TYPE_ASSISTANT
                    && WELCOME_MESSAGE.equals(msg.getContent())) {
                continue;
            }
            toSave.add(msg);
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
        chatMessages.add(ChatUiMessage.loading());

        currentThinkingMessage = null;
        thinkingJustCreated = false;
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
        pendingState = null;
        pendingStreamItems = null;
        streamFinished = false;
        itemFlushScheduled = false;
        streamingProductList.clear();
        chatSseClient.streamChat(sessionId, message, new ChatSseClient.StreamListener() {
            @Override
            public void onTextDelta(String content) {
                mainHandler.post(() -> appendStreamingText(content));
            }

            @Override
            public void onState(String stateJson) {
                mainHandler.post(() -> {
                    try {
                        pendingState = gson.fromJson(stateJson,
                                new TypeToken<Map<String, Object>>() {}.getType());
                        if (pendingState != null) {
                            Object rc = pendingState.get("result_count");
                            if (rc instanceof Double) {
                                pendingResultCount = ((Double) rc).intValue();
                            }
                        }
                        // state 到达，仅记录；产品在 done 后才统一展示
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                });
            }

            @Override
            public void onItems(List<RecommendResponse.Item> items, int resultCount) {
                // 不再使用独立的 items 事件，全部由 card 事件驱动
            }

            @Override
            public void onCard(com.google.gson.JsonObject itemData) {
                mainHandler.post(() -> onCardEvent(itemData));
            }

            @Override
            public void onThinking(String event, String node, String detail) {
                mainHandler.post(() -> onThinkingEvent(event, node, detail));
            }

            @Override
            public void onDone() {
                mainHandler.post(() -> {
                    streamFinished = true;
                });
            }

            @Override
            public void onError(String errorMessage) {
                mainHandler.post(() -> {
                    streamFinished = true;
                    mainHandler.removeCallbacks(itemFlushTask);
                    itemFlushScheduled = false;
                    streamingProductList.clear();
                    drainStreamingBuffer();
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
        // 标记思考链完成，此后允许收起
        if (currentThinkingMessage != null) {
            currentThinkingMessage.setThinkingComplete(true);
        }

        // 思考链刚创建，等一帧再处理文字
        if (thinkingJustCreated) {
            rvChat.postDelayed(() -> appendStreamingText(delta), 150);
            return;
        }

        if (streamingAssistantIndex < 0 || streamingAssistantIndex >= chatMessages.size()) {
            ChatUiMessage assistant = ChatUiMessage.assistant("");
            assistant.setStreaming(true);
            chatMessages.add(assistant);
            streamingAssistantIndex = chatMessages.size() - 1;
        }

        streamingBuffer.append(delta);
        scheduleStreamingFlush();
    }

    /**
     * 幂等调度：如果还没有排空的定时任务，就 postDelayed 一个。
     */
    private void scheduleStreamingFlush() {
        if (!flushScheduled) {
            flushScheduled = true;
            mainHandler.postDelayed(flushTask, FLUSH_INTERVAL_MS);
        }
    }

    /**
     * 强制排空缓冲区：取消定时器，把剩余内容一次性追加到 assistant 气泡。
     */
    private void drainStreamingBuffer() {
        mainHandler.removeCallbacks(flushTask);
        if (streamingBuffer.length() > 0) {
            String remaining = streamingBuffer.toString();
            streamingBuffer.setLength(0);
            if (streamingAssistantIndex >= 0 && streamingAssistantIndex < chatMessages.size()) {
                ChatUiMessage assistant = chatMessages.get(streamingAssistantIndex);
                assistant.appendContent(remaining);
                chatAdapter.notifyItemChanged(streamingAssistantIndex);
            }
        }
        flushScheduled = false;
    }

    /**
     * 幂等调度 itemFlushTask：只在未调度且有缓冲 items 时启动逐条展示。
     */
    private void scheduleItemFlush() {
        if (!itemFlushScheduled && pendingStreamItems != null && !pendingStreamItems.isEmpty()) {
            itemFlushScheduled = true;
            mainHandler.postDelayed(itemFlushTask, ITEM_FLUSH_INTERVAL_MS);
        }
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

    private void appendCompareItems(List<RecommendResponse.Item> items) {
        if (items == null || items.isEmpty()) {
            return;
        }
        int index = 1;
        for (RecommendResponse.Item item : items) {
            chatMessages.add(ChatUiMessage.compareProduct(toProduct(item), index));
            index++;
        }
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
            if (isCurrentAction("compare")) {
                assistant.setContent(formatCompareReply(assistant.getContent()));
            }
            chatAdapter.notifyItemChanged(streamingAssistantIndex);
        }
        streamingAssistantIndex = -1;
        // 思考链保留在对话中，不删除
        setSendingState(false);
        scrollToBottom();
    }

    // ========== REST 响应处理 ==========

    private void handleChatResponse(ChatResponse response) {
        removeLoadingMessage();
        if (response.getSession_id() != null) {
            sessionId = response.getSession_id();
            prefs.edit().putString(KEY_SESSION_ID, sessionId).apply();
        }

        // 优先 content_blocks（LLM 驱动，文本卡片交替）
        List<Map<String, Object>> blocks = response.getContent_blocks();
        if (blocks != null && !blocks.isEmpty()) {
            for (Map<String, Object> block : blocks) {
                if ("text".equals(block.get("type"))) {
                    String t = (String) block.get("content");
                    chatMessages.add(ChatUiMessage.assistant(t != null ? t : ""));
                } else if ("card".equals(block.get("type"))) {
                    Map<String, Object> itemData = (Map<String, Object>) block.get("item");
                    if (itemData != null) {
                        RecommendResponse.Item item = gson.fromJson(
                                gson.toJson(itemData), RecommendResponse.Item.class);
                        List<Product> list = new ArrayList<>();
                        list.add(toProduct(item));
                        chatMessages.add(ChatUiMessage.productRow(list));
                    }
                }
            }
        } else {
            String reply = response.getReply();
            chatMessages.add(ChatUiMessage.assistant(
                    reply != null && !reply.isEmpty() ? reply : "已完成处理。"));
        }

        chatAdapter.notifyDataSetChanged();
        scrollToBottom();
        setSendingState(false);
    }

    // ========== 工具方法 ==========

    private void removeThinkingMessage() {
        if (currentThinkingMessage != null) {
            int idx = chatMessages.indexOf(currentThinkingMessage);
            if (idx >= 0) {
                chatMessages.remove(idx);
                chatAdapter.notifyItemRemoved(idx);
            }
        }
        currentThinkingMessage = null;
    }

    /** 刷新思考链列表里所有 item 的索引（在 done 后调用一次） */

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
        product.setSku_id(item.getSku_id());
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
        if (pendingItemsCount > 0 && !isCurrentAction("compare")) {
            int totalCount = pendingResultCount > 0 ? pendingResultCount : pendingItemsCount;
            String text;
            if (totalCount > pendingItemsCount) {
                text = "共找到 " + totalCount + " 件，已为你推荐 " + pendingItemsCount + " 款";
            } else {
                text = "已为你推荐 " + pendingItemsCount + " 款";
            }
            chatMessages.add(ChatUiMessage.divider(text));
            chatAdapter.notifyItemInserted(chatMessages.size() - 1);
            scrollToBottom();
        }
    }

    private boolean isCurrentAction(String action) {
        if (pendingState == null) {
            return false;
        }
        Object currentAction = pendingState.get("action");
        return action.equals(currentAction);
    }

    private String formatCompareReply(String reply) {
        if (reply == null || reply.isEmpty()) {
            return reply;
        }
        String formatted = reply
                .replace("。", "。\n\n")
                .replace("；", "；\n")
                .replace("，如果", "\n\n如果")
                .replace("，但", "\n但")
                .trim();
        return formatted
                .replace("优点：", "**优点：**")
                .replace("优势：", "**优势：**")
                .replace("不足：", "**不足：**")
                .replace("缺点：", "**缺点：**")
                .replace("结论：", "**结论：**")
                .replace("依据是", "**依据是**")
                .replace("如果预算", "**如果预算**")
                .replace("更合适", "**更合适**");
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

    // ========== SSE 思考链 ==========

    /**
     * card SSE 事件：LLM 提到了某个商品，直接在当前对话流中插入商品卡片。
     */
    private void onCardEvent(com.google.gson.JsonObject itemData) {
        RecommendResponse.Item item = gson.fromJson(itemData, RecommendResponse.Item.class);
        if (item == null) return;
        Product product = toProduct(item);
        List<Product> list = new ArrayList<>();
        list.add(product);
        chatMessages.add(ChatUiMessage.productRow(list));
        chatAdapter.notifyItemInserted(chatMessages.size() - 1);
        scrollToBottom();
    }

    private void onThinkingEvent(String event, String node, String detail) {
        String label;
        if ("done".equals(event) && detail != null && !detail.isEmpty()) {
            label = detail;
        } else {
            label = mapNodeLabel(node);
        }

        if (currentThinkingMessage == null) {
            removeLoadingMessage();
            currentThinkingMessage = ChatUiMessage.thinking();
            chatMessages.add(currentThinkingMessage);
            chatAdapter.notifyDataSetChanged();
            thinkingJustCreated = true;
            scrollToBottom();
            // 等一帧让 RecyclerView 渲染完再处理 delta
            rvChat.post(() -> thinkingJustCreated = false);
            return;
        }

        if (currentThinkingMessage != null) {
            currentThinkingMessage.addThinkingStep(label);
            int idx = chatMessages.indexOf(currentThinkingMessage);
            if (idx >= 0) {
                // 每一步延迟一帧渲染，让用户看到渐进过程
                rvChat.postDelayed(() -> chatAdapter.notifyItemChanged(idx), 50);
            }
        }
        scrollToBottom();
    }

    private String mapNodeLabel(String node) {
        switch (node) {
            case "understand_user": return "理解需求";
            case "decide_next_action": return "规划动作";
            case "execute_action": return "检索商品";
            case "generate_reply": return "生成回复";
            case "finalize_response": return "整理回复";
            default: return node;
        }
    }

    // ========== SSE items 缓冲 & 对比卡片构建 ==========

    /**
     * 兜底：取消逐条定时器，一次性展示剩余缓冲 items（用于 done / error 收尾）。
     */
    private void processPendingStreamItems() {
        mainHandler.removeCallbacks(itemFlushTask);
        itemFlushScheduled = false;
        // 先把推荐模式累积的 product 刷出
        flushStreamingProductRow();
        if (pendingStreamItems == null || pendingStreamItems.isEmpty()) return;
        if (isCurrentAction("compare")) {
            appendCompareItems(pendingStreamItems);
        } else {
            appendProductItems(pendingStreamItems);
        }
        pendingStreamItems = null;
    }

    private void addProductToServerCart(Product product) {
        String skuId = product.getSku_id();
        if (skuId == null || skuId.trim().isEmpty()) {
            Toast.makeText(this, "该商品暂无可购买 SKU", Toast.LENGTH_SHORT).show();
            return;
        }
        new Thread(() -> {
            try {
                backendApiClient.addToCart(sessionId, skuId);
                runOnUiThread(() -> Toast.makeText(this,
                        product.getTitle() + " 已加入购物车", Toast.LENGTH_SHORT).show());
            } catch (IOException error) {
                runOnUiThread(() -> Toast.makeText(this,
                        error.getMessage(), Toast.LENGTH_LONG).show());
            }
        }, "shopguide-add-cart").start();
    }

    private void handleSelectedImage(Uri uri) {
        Toast.makeText(this, "正在理解图片…", Toast.LENGTH_SHORT).show();
        new Thread(() -> {
            try (InputStream input = getContentResolver().openInputStream(uri);
                 java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream()) {
                if (input == null) throw new IOException("无法读取图片");
                byte[] buffer = new byte[8192];
                int count;
                while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                String mimeType = getContentResolver().getType(uri);
                if (mimeType == null) mimeType = "image/jpeg";
                byte[] image = output.toByteArray();
                String description = null;
                String failure = null;
                List<Product> similar = new ArrayList<>();
                try {
                    description = backendApiClient.understandImage(image, mimeType);
                } catch (IOException error) {
                    failure = error.getMessage();
                }
                try {
                    similar = backendApiClient.searchSimilar(image, mimeType, 5);
                } catch (IOException error) {
                    if (failure == null) failure = error.getMessage();
                }
                String finalDescription = description;
                String finalFailure = failure;
                List<Product> finalSimilar = similar;
                runOnUiThread(() -> {
                    if (finalDescription != null && !finalDescription.trim().isEmpty()) {
                        chatMessages.add(ChatUiMessage.assistant("图片识别：" + finalDescription));
                        etMessage.setText("请根据这张图片帮我找相似商品：" + finalDescription);
                        etMessage.setSelection(etMessage.length());
                    }
                    if (!finalSimilar.isEmpty()) {
                        chatMessages.add(ChatUiMessage.productRow(finalSimilar));
                    }
                    if (finalDescription != null || !finalSimilar.isEmpty()) {
                        chatAdapter.notifyDataSetChanged();
                        scrollToBottom();
                    } else {
                        Toast.makeText(this, finalFailure != null ? finalFailure : "图片能力未配置",
                                Toast.LENGTH_LONG).show();
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> Toast.makeText(this,
                        error.getMessage(), Toast.LENGTH_LONG).show());
            }
        }, "shopguide-image-understand").start();
    }

    private void speakText(String text) {
        new Thread(() -> {
            try {
                byte[] audio = backendApiClient.synthesize(text);
                File file = new File(getCacheDir(), "tts-" + UUID.randomUUID() + ".mp3");
                try (FileOutputStream output = new FileOutputStream(file)) {
                    output.write(audio);
                }
                runOnUiThread(() -> {
                    try {
                        if (mediaPlayer != null) mediaPlayer.release();
                        mediaPlayer = new MediaPlayer();
                        mediaPlayer.setDataSource(file.getAbsolutePath());
                        mediaPlayer.setOnCompletionListener(player -> {
                            player.release();
                            if (mediaPlayer == player) mediaPlayer = null;
                            file.delete();
                        });
                        mediaPlayer.prepare();
                        mediaPlayer.start();
                    } catch (IOException error) {
                        speakWithDeviceTts(text);
                    }
                });
            } catch (IOException error) {
                runOnUiThread(() -> speakWithDeviceTts(text));
            }
        }, "shopguide-tts").start();
    }

    private void speakWithDeviceTts(String text) {
        if (tts == null) return;
        tts.setLanguage(Locale.CHINESE);
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, null);
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
            if (selected.size() < 2) {
                Toast.makeText(this, "请至少选择两个商品进行对比", Toast.LENGTH_SHORT).show();
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

        sheetView.findViewById(R.id.btnCartCheckout).setOnClickListener(v -> {
            v.setEnabled(false);
            new Thread(() -> {
                try {
                    String orderId = backendApiClient.checkout(sessionId);
                    runOnUiThread(() -> {
                        cartProducts.clear();
                        sheet.dismiss();
                        Toast.makeText(this, "模拟下单成功，订单号：" + orderId,
                                Toast.LENGTH_LONG).show();
                    });
                } catch (IOException error) {
                    runOnUiThread(() -> {
                        v.setEnabled(true);
                        Toast.makeText(this, error.getMessage(), Toast.LENGTH_LONG).show();
                    });
                }
            }, "shopguide-checkout").start();
        });

        sheet.show();
    }

    static class CartProductAdapter extends RecyclerView.Adapter<CartProductAdapter.Vh> {
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
                        .data(new BackendApiClient().absoluteUrl(url))
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
