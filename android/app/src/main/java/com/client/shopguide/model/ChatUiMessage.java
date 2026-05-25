package com.client.shopguide.model;

import java.util.List;

/**
 * 对话列表 UI 模型，支持用户气泡、AI 回复、产品行（横向卡片）、和加载态
 */
public class ChatUiMessage {

    public static final int TYPE_USER = 0;
    public static final int TYPE_ASSISTANT = 1;
    public static final int TYPE_PRODUCT = 2;
    public static final int TYPE_LOADING = 3;
    public static final int TYPE_PRODUCT_ROW = 4;

    private final int type;
    private String content;
    private Product product;
    private List<Product> productList;
    private boolean streaming;

    public ChatUiMessage(int type, String content) {
        this.type = type;
        this.content = content;
    }

    public static ChatUiMessage user(String content) {
        return new ChatUiMessage(TYPE_USER, content);
    }

    public static ChatUiMessage assistant(String content) {
        return new ChatUiMessage(TYPE_ASSISTANT, content);
    }

    public static ChatUiMessage product(Product product) {
        ChatUiMessage message = new ChatUiMessage(TYPE_PRODUCT, "");
        message.product = product;
        return message;
    }

    public static ChatUiMessage productRow(List<Product> productList) {
        ChatUiMessage message = new ChatUiMessage(TYPE_PRODUCT_ROW, "");
        message.productList = productList;
        return message;
    }

    public static ChatUiMessage loading() {
        return new ChatUiMessage(TYPE_LOADING, "正在思考...");
    }

    public int getType() {
        return type;
    }

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public void appendContent(String delta) {
        if (content == null) {
            content = delta;
        } else {
            content += delta;
        }
    }

    public Product getProduct() {
        return product;
    }

    public List<Product> getProductList() {
        return productList;
    }

    public boolean isStreaming() {
        return streaming;
    }

    public void setStreaming(boolean streaming) {
        this.streaming = streaming;
    }
}
