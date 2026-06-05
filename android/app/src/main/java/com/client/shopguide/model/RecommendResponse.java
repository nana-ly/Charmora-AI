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
        private String price_range;
        private String reason;
        private String evidence;
        private String image_url;
        private float rating;
        private int sold_count;
        private int review_count;
        private String marketing_desc;
        private List<ReviewItem> reviews;
        private List<FaqItem> faqs;

        public Item() {
        }

        public String getProduct_id() { return product_id; }
        public void setProduct_id(String product_id) { this.product_id = product_id; }

        public String getTitle() { return title; }
        public void setTitle(String title) { this.title = title; }

        public String getBrand() { return brand; }
        public void setBrand(String brand) { this.brand = brand; }

        public double getPrice() { return price; }
        public void setPrice(double price) { this.price = price; }

        public String getPrice_range() { return price_range; }
        public void setPrice_range(String price_range) { this.price_range = price_range; }

        public String getReason() { return reason; }
        public void setReason(String reason) { this.reason = reason; }

        public String getEvidence() { return evidence; }
        public void setEvidence(String evidence) { this.evidence = evidence; }

        public String getImage_url() { return image_url; }
        public void setImage_url(String image_url) { this.image_url = image_url; }

        public float getRating() { return rating; }
        public void setRating(float rating) { this.rating = rating; }

        public int getSold_count() { return sold_count; }
        public void setSold_count(int sold_count) { this.sold_count = sold_count; }

        public int getReview_count() { return review_count; }
        public void setReview_count(int review_count) { this.review_count = review_count; }

        public String getMarketing_desc() { return marketing_desc; }
        public void setMarketing_desc(String marketing_desc) { this.marketing_desc = marketing_desc; }

        public List<ReviewItem> getReviews() { return reviews; }
        public void setReviews(List<ReviewItem> reviews) { this.reviews = reviews; }

        public List<FaqItem> getFaqs() { return faqs; }
        public void setFaqs(List<FaqItem> faqs) { this.faqs = faqs; }
    }
}
