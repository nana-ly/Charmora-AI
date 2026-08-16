package com.client.shopguide.model;

import java.util.ArrayList;
import java.util.List;

public class OrderSnapshot {
    public String id;
    public String sessionId;
    public String status;
    public double totalAmount;
    public String paymentMethod;
    public String paymentStatus;
    public String recipientName;
    public String recipientPhone;
    public String shippingAddress;
    public String createdAt;
    public List<Event> statusEvents = new ArrayList<>();

    public static class Event {
        public String fromStatus;
        public String toStatus;
        public String reason;
        public String createdAt;
    }
}
