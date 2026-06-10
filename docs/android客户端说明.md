# Android 客户端说明

## 概览

ShopGuide Android 客户端是一个基于 Java 的原生应用，对接后端 FastAPI 服务，提供多轮智能导购对话体验。

- **包名：** `com.client.shopguide`
- **最低 SDK：** 24 (Android 7.0)
- **目标 SDK：** 36
- **语言：** Java 11

---

## 项目结构

```
android/app/src/main/
├── AndroidManifest.xml
├── java/com/client/shopguide/
│   ├── MainActivity.java          # 主对话页
│   ├── ProductDetailActivity.java # 商品详情页
│   ├── RetrofitClient.java        # 网络层（OkHttp + Retrofit）
│   ├── ApiService.java            # API 接口定义
│   ├── adapter/
│   │   ├── ChatAdapter.java       # 对话列表适配器（7 种 ViewType）
│   │   └── ProductCardAdapter.java # 商品横滚卡片适配器
│   ├── model/                     # 数据模型
│   ├── network/
│   │   └── ChatSseClient.java     # SSE 流式对话客户端
│   └── voice/
│       └── BaiduAsrClient.java    # 百度语音识别
└── res/
    ├── layout/                    # 布局文件
    ├── drawable/                  # 背景、图标等
    ├── mipmap-*/                  # 应用图标（6 种密度）
    └── values/                    # 颜色、字符串、主题
```

---

## 架构与数据流

### 对话流程

```
用户输入文字/语音
    │
    ▼
MainActivity.sendCurrentMessage()
    │
    ├─ 优先：SSE 流式 (POST /chat/stream)
    │     ChatSseClient → start → delta(文本) → items(商品) → state(意图/动作) → done
    │     MainActivity 缓冲 items，等 state 到达后判断展示方式：
    │       ├─ state.action == "compare" → 双列对比卡片
    │       └─ 其他                      → 商品横滚卡片
    │
    └─ 回退：REST (POST /chat)
          Retrofit → ChatResponse → 同上判断
```

### SSE 事件处理

| 事件 | 数据 | 处理 |
|------|------|------|
| `start` | session_id | 确认连接 |
| `delta` | text 片段 | 流式追加到 AI 气泡 |
| `items` | 商品列表 | **缓冲**，等 state 后决定展示方式 |
| `state` | intent/action/result_count 等 | 解析 action，刷新缓冲 items |
| `done` | - | 结束流式，兜底刷新缓冲 |
| `error` | message | 显示错误内容 |

### 支持的后端动作

| action | 展示方式 | 说明 |
|--------|---------|------|
| `recommend` | 商品横滚卡片 + 文本回复 | 推荐结果 |
| `compare` | 双列对比卡片 + 文本回复 | 对比两个商品 |
| `explain` | 纯文本回复 | 解释某个商品 |
| `clarify` | 纯文本回复 | 追问更多信息 |
| `reply_only` | 纯文本回复 | 仅回复文案 |

---

## 关键类说明

### MainActivity — 主对话页

- 管理会话 ID（SharedPreferences 持久化，超时 5 分钟自动新建）
- 对话历史本地存入 `chat_messages.json`
- 集成 TTS 语音播报（长按 AI 消息触发）
- 集成百度语音输入（ASR，16kHz PCM 录音 + VAD 静音检测）
- 集成拍照/相册选图（TODO：上传接口待后端提供）
- 购物车（客户端本地列表，支持多选后发起比较）

### ChatSseClient — SSE 流式客户端

- 基于 OkHttp 的 `text/event-stream` 解析
- 自动 fallback：404/405 时回退到 REST `/chat` 接口
- 后台线程解析 SSE，通过 mainHandler post 回主线程更新 UI

### ChatAdapter — 对话列表适配器

支持 7 种 ViewType：

| Type | 布局 | 说明 |
|------|------|------|
| `TYPE_USER` | 用户气泡 | 右对齐，浅色背景 |
| `TYPE_ASSISTANT` | AI 气泡 | 左对齐，支持流式光标、长按 TTS |
| `TYPE_PRODUCT_ROW` | 商品横滚 | Horizontal RecyclerView |
| `TYPE_PRODUCT` | 单商品卡片 | 图片 + 标题 + 价格 + 加购 |
| `TYPE_COMPARE` | 对比卡片 | 左右双列 VS 对比 |
| `TYPE_DIVIDER` | 分割线 | 时间或结果计数 |
| `TYPE_LOADING` | 加载动画 | 三点波浪动画 |

### ProductDetailActivity — 商品详情页

- 大图 + 品牌 + 价格区间 + 评分 + 销量 + 推荐理由 + 匹配依据
- 用户评论（折叠展开，头像彩色圆角）
- FAQ 手风琴折叠
- 加入购物车按钮

---

## 配置

### 服务器地址

修改 `RetrofitClient.java`、`ProductCardAdapter.java`、`ProductDetailActivity.java` 中的 BASE_URL：

```java
// 模拟器本地后端
private static final String BASE_URL = "http://10.0.2.2:8000/";

// 部署服务器（生产用）
private static final String BASE_URL = "http://8.137.191.215/";
```

### 百度语音识别

在 `android/.env` 配置（不纳入版本控制）：

```properties
BAIDU_APP_ID=your_app_id
BAIDU_API_KEY=your_api_key
BAIDU_SECRET_KEY=your_secret_key
```

---

## 构建与运行

1. Android Studio 打开 `android/` 目录
2. Sync Gradle
3. 配置 `.env`（语音识别凭证）
4. Run → 选择设备或模拟器

```bash
# 命令行构建
cd android
./gradlew assembleDebug
```

---

## 依赖

| 库 | 版本 | 用途 |
|----|------|------|
| Retrofit + Gson | 2.9.0 | HTTP 请求 + JSON 解析 |
| OkHttp Logging | 4.12.0 | 网络日志 |
| Coil | 2.6.0 | 图片加载 |
| Material3 | 1.11.0 | UI 组件 |
| RecyclerView | 1.3.2 | 列表 |
| CardView | 1.0.0 | 卡片容器 |

---

## 已知限制

- 拍照/相册上传功能 UI 已就绪，等待后端图片接口
- 购物车仅在客户端本地存储，不同步后端
- 对比卡片当前只展示前两个商品
- 系统闪屏是 Android 12+ 强制行为，无法绕过或添加文字，仅可替换图标
