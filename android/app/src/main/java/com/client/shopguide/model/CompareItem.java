package com.client.shopguide.model;

import java.util.List;

/**
 * 对比卡片中的单个商品条目
 */
public class CompareItem {

    private String name;
    private String price;
    private List<String> pros;
    private List<String> cons;

    public CompareItem() {
    }

    public CompareItem(String name, String price, List<String> pros, List<String> cons) {
        this.name = name;
        this.price = price;
        this.pros = pros;
        this.cons = cons;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getPrice() {
        return price;
    }

    public void setPrice(String price) {
        this.price = price;
    }

    public List<String> getPros() {
        return pros;
    }

    public void setPros(List<String> pros) {
        this.pros = pros;
    }

    public List<String> getCons() {
        return cons;
    }

    public void setCons(List<String> cons) {
        this.cons = cons;
    }
}
