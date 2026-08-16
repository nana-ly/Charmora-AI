package com.client.shopguide.model;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

public class StorePresentationTest {
    @Test
    public void mapsOrderTimelineStatuses() {
        assertEquals("待确认", StorePresentation.statusLabel("created"));
        assertEquals("模拟支付成功", StorePresentation.statusLabel("paid"));
        assertEquals("备货中", StorePresentation.statusLabel("preparing"));
        assertEquals("已完成", StorePresentation.statusLabel("completed"));
        assertEquals("已取消", StorePresentation.statusLabel("cancelled"));
    }

    @Test
    public void mapsSimulatedPaymentMethods() {
        assertEquals("微信演示支付", StorePresentation.paymentLabel("demo_wechat"));
        assertEquals("支付宝演示支付", StorePresentation.paymentLabel("demo_alipay"));
        assertEquals("银行卡演示支付", StorePresentation.paymentLabel("demo_bank_card"));
    }
}
