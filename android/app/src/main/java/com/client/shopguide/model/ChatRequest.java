package com.client.shopguide.model;

/**
 * 多轮对话请求体，匹配后端 POST /chat 与 POST /chat/stream
 */
public class ChatRequest {

    private String session_id;
    private String message;

    public ChatRequest(String session_id, String message) {
        this.session_id = session_id;
        this.message = message;
    }

    public String getSession_id() {
        return session_id;
    }

    public void setSession_id(String session_id) {
        this.session_id = session_id;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }
}
