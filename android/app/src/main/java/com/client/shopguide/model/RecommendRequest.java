package com.client.shopguide.model;

/**
 * 推荐请求体
 */
public class RecommendRequest {

    private String query;

    public RecommendRequest() {
    }

    public RecommendRequest(String query) {
        this.query = query;
    }

    public String getQuery() {
        return query;
    }

    public void setQuery(String query) {
        this.query = query;
    }
}
