package com.client.shopguide.model;

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
}
