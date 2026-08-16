package com.client.shopguide.model;

public final class StorePresentation {
    private StorePresentation() {}

    public static String statusLabel(String value) {
        if ("preparing".equals(value)) return "备货中";
        if ("completed".equals(value)) return "已完成";
        if ("cancelled".equals(value)) return "已取消";
        if ("paid".equals(value)) return "模拟支付成功";
        return "待确认";
    }

    public static String paymentLabel(String value) {
        if ("demo_alipay".equals(value)) return "支付宝演示支付";
        if ("demo_bank_card".equals(value)) return "银行卡演示支付";
        return "微信演示支付";
    }
}
