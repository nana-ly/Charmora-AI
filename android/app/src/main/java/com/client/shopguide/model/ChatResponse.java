package com.client.shopguide.model;

import java.util.List;
import java.util.Map;

/**
 * 多轮对话响应体，匹配后端 POST /chat
 */
public class ChatResponse {

    private String session_id;
    private String reply;
    private int result_count;
    private List<RecommendResponse.Item> items;
    private Map<String, Object> state;

    public ChatResponse() {
    }

    public String getSession_id() {
        return session_id;
    }

    public void setSession_id(String session_id) {
        this.session_id = session_id;
    }

    public String getReply() {
        return reply;
    }

    public void setReply(String reply) {
        this.reply = reply;
    }

    public int getResult_count() { return result_count; }
    public void setResult_count(int result_count) { this.result_count = result_count; }

    public List<RecommendResponse.Item> getItems() {
        return items;
    }

    public void setItems(List<RecommendResponse.Item> items) {
        this.items = items;
    }

    public Map<String, Object> getState() {
        return state;
    }

    public void setState(Map<String, Object> state) {
        this.state = state;
    }
}
