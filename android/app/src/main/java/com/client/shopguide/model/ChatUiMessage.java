package com.client.shopguide.model;

import java.util.ArrayList;
import java.util.List;

/**
 * 对话列表 UI 模型，支持用户气泡、AI 回复、产品行和加载态
 */
public class ChatUiMessage {

    public static final int TYPE_USER = 0;
    public static final int TYPE_ASSISTANT = 1;
    public static final int TYPE_PRODUCT = 2;
    public static final int TYPE_LOADING = 3;
    public static final int TYPE_PRODUCT_ROW = 4;
    public static final int TYPE_COMPARE_PRODUCT = 5;
    public static final int TYPE_THINKING = 7;
    public static final int TYPE_DIVIDER = 6;

    private final int type;
    private String content;
    private transient CharSequence styledContent;
    private Product product;
    private List<Product> productList;
    private final List<String> thinkingSteps = new ArrayList<>(); // 思考链步骤
    private boolean thinkingExpanded;
    private boolean thinkingComplete;
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

    public static ChatUiMessage compareProduct(Product product, int index) {
        ChatUiMessage message = new ChatUiMessage(TYPE_COMPARE_PRODUCT, "对比商品 " + index);
        message.product = product;
        return message;
    }

    public static ChatUiMessage loading() {
        return new ChatUiMessage(TYPE_LOADING, "正在思考...");
    }

    public static ChatUiMessage thinking() {
        return new ChatUiMessage(TYPE_THINKING, "");
    }

    public void addThinkingStep(String step) { thinkingSteps.add(step); }
    public List<String> getThinkingSteps() { return thinkingSteps; }
    public boolean isThinkingExpanded() { return thinkingExpanded; }
    public void setThinkingExpanded(boolean v) { thinkingExpanded = v; }
    public boolean isThinkingComplete() { return thinkingComplete; }
    public void setThinkingComplete(boolean v) { thinkingComplete = v; }

    public static ChatUiMessage divider(String time) {
        return new ChatUiMessage(TYPE_DIVIDER, time);
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

    public CharSequence getStyledContent() {
        return styledContent;
    }

    public void setStyledContent(CharSequence styledContent) {
        this.styledContent = styledContent;
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
