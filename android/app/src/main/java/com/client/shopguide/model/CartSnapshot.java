package com.client.shopguide.model;

import java.util.ArrayList;
import java.util.List;

public class CartSnapshot {
    public String sessionId;
    public double totalAmount;
    public String currency = "CNY";
    public List<Item> items = new ArrayList<>();

    public static class Item {
        public String skuId;
        public String productId;
        public String title;
        public String skuName;
        public int quantity;
        public int availableQuantity;
        public double unitPrice;
        public String imageUrl;
    }
}
