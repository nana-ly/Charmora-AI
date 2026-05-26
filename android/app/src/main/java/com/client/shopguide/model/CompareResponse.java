package com.client.shopguide.model;

/**
 * 对比卡片响应模型，包含左右两个对比商品
 */
public class CompareResponse {

    private CompareItem leftItem;
    private CompareItem rightItem;

    public CompareResponse() {
    }

    public CompareResponse(CompareItem leftItem, CompareItem rightItem) {
        this.leftItem = leftItem;
        this.rightItem = rightItem;
    }

    public CompareItem getLeftItem() {
        return leftItem;
    }

    public void setLeftItem(CompareItem leftItem) {
        this.leftItem = leftItem;
    }

    public CompareItem getRightItem() {
        return rightItem;
    }

    public void setRightItem(CompareItem rightItem) {
        this.rightItem = rightItem;
    }
}
