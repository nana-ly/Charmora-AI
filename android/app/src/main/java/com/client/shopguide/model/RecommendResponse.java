package com.client.shopguide.model;

import java.util.List;

/**
 * 推荐响应体
 */
public class RecommendResponse {

    private String query;
    private Filters filters;
    private String answer;
    private List<Product> products;

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

    public String getAnswer() {
        return answer;
    }

    public void setAnswer(String answer) {
        this.answer = answer;
    }

    public List<Product> getProducts() {
        return products;
    }

    public void setProducts(List<Product> products) {
        this.products = products;
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
}
