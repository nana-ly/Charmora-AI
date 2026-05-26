package com.client.shopguide.model;

import java.util.List;

/**
 * 商品数据模型
 */
public class Product {

    private String product_id;
    private String title;
    private String brand;
    private String category;
    private String sub_category;
    private double base_price;
    private String reason;
    private String matched_evidence;

    // ========== 预留字段（等后端返回真实数据） ==========
    // TODO: 后端返回真实 imageUrl、rating、soldCount、tags 后移除 Mock 默认值
    private String imageUrl;          // 商品图片URL
    private float rating;             // 评分 0~5
    private int soldCount;            // 销量
    private List<String> tags;        // 标签列表，如 "热销"、"新品"、"包邮"

    public Product() {
    }

    public Product(String product_id, String title, String brand, String category,
                   String sub_category, double base_price, String reason, String matched_evidence) {
        this.product_id = product_id;
        this.title = title;
        this.brand = brand;
        this.category = category;
        this.sub_category = sub_category;
        this.base_price = base_price;
        this.reason = reason;
        this.matched_evidence = matched_evidence;
    }

    // ========== 原有字段 ==========

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

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getSub_category() {
        return sub_category;
    }

    public void setSub_category(String sub_category) {
        this.sub_category = sub_category;
    }

    public double getBase_price() {
        return base_price;
    }

    public void setBase_price(double base_price) {
        this.base_price = base_price;
    }

    public String getReason() {
        return reason;
    }

    public void setReason(String reason) {
        this.reason = reason;
    }

    public String getMatched_evidence() {
        return matched_evidence;
    }

    public void setMatched_evidence(String matched_evidence) {
        this.matched_evidence = matched_evidence;
    }

    // ========== 预留字段 getter/setter ==========

    public String getImageUrl() {
        return imageUrl;
    }

    public void setImageUrl(String imageUrl) {
        this.imageUrl = imageUrl;
    }

    public float getRating() {
        return rating;
    }

    public void setRating(float rating) {
        this.rating = rating;
    }

    public int getSoldCount() {
        return soldCount;
    }

    public void setSoldCount(int soldCount) {
        this.soldCount = soldCount;
    }

    public List<String> getTags() {
        return tags;
    }

    public void setTags(List<String> tags) {
        this.tags = tags;
    }
}
