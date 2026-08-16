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
    private List<Map<String, Object>> content_blocks;

    public ChatResponse() {}

    public String getSession_id() { return session_id; }
    public void setSession_id(String v) { session_id = v; }

    public String getReply() { return reply; }
    public void setReply(String v) { reply = v; }

    public int getResult_count() { return result_count; }
    public void setResult_count(int v) { result_count = v; }

    public List<RecommendResponse.Item> getItems() { return items; }
    public void setItems(List<RecommendResponse.Item> v) { items = v; }

    public Map<String, Object> getState() { return state; }
    public void setState(Map<String, Object> v) { state = v; }

    public List<Map<String, Object>> getContent_blocks() { return content_blocks; }
    public void setContent_blocks(List<Map<String, Object>> v) { content_blocks = v; }
}
