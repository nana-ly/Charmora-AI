package com.client.shopguide.model;

import java.util.List;

/**
 * 推荐响应体，匹配后端 /recommend 返回格式
 */
public class RecommendResponse {

    private String query;
    private Filters filters;
    private List<Item> items;

    public RecommendResponse() {
    }

    public String getQuery() {
        return query;
    }

    public void setQuery(String query) {
        this.query = query;
    }

    public Filters getFilters() {
        return filters;
    }

    public void setFilters(Filters filters) {
        this.filters = filters;
    }

    public List<Item> getItems() {
        return items;
    }

    public void setItems(List<Item> items) {
        this.items = items;
    }

    /**
     * 筛选条件
     */
    public static class Filters {
        private String category;
        private Double max_price;
        private String brand;
        private List<String> keywords;

        public Filters() {
        }

        public String getCategory() {
            return category;
        }

        public void setCategory(String category) {
            this.category = category;
        }

        public Double getMax_price() {
            return max_price;
        }

        public void setMax_price(Double max_price) {
            this.max_price = max_price;
        }

        public String getBrand() {
            return brand;
        }

        public void setBrand(String brand) {
            this.brand = brand;
        }

        public List<String> getKeywords() {
            return keywords;
        }

        public void setKeywords(List<String> keywords) {
            this.keywords = keywords;
        }
    }

    /**
     * 后端返回的单条商品数据，字段与后端 recommendation.py 一致
     */
    public static class Item {
        private String product_id;
        private String title;
        private String brand;
        private double price;
        private String reason;
        private String evidence;

        public Item() {
        }

        public String getProduct_id() {
            return product_id;
        }

        public void setProduct_id(String product_id) {
            this.product_id = product_id;
        }

        public String getTitle() {
            return title;
        }

        public void setTitle(String title) {
            this.title = title;
        }

        public String getBrand() {
            return brand;
        }

        public void setBrand(String brand) {
            this.brand = brand;
        }

        public double getPrice() {
            return price;
        }

        public void setPrice(double price) {
            this.price = price;
        }

        public String getReason() {
            return reason;
        }

        public void setReason(String reason) {
            this.reason = reason;
        }

        public String getEvidence() {
            return evidence;
        }

        public void setEvidence(String evidence) {
            this.evidence = evidence;
        }
    }
}
