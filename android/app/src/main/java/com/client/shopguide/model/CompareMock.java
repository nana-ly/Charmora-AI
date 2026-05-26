package com.client.shopguide.model;

import java.util.Arrays;

/**
 * 对比卡片 Mock 数据
 * TODO: 等后端 /compare 接口 ready 后，替换为真实 API 调用
 */
public class CompareMock {

    /**
     * 返回 Mock 对比数据用于 UI 展示
     */
    public static CompareResponse getMockData() {
        CompareItem left = new CompareItem(
                "华为 Mate 60 Pro",
                "¥6999",
                Arrays.asList("卫星通话", "昆仑玻璃", "XMAGE影像"),
                Arrays.asList("价格偏高", "重量较大", "5G仅特定版本")
        );

        CompareItem right = new CompareItem(
                "小米 14 Pro",
                "¥4999",
                Arrays.asList("徕卡光学镜头", "骁龙8 Gen3", "120W快充"),
                Arrays.asList("系统广告较多", "长焦一般", "无卫星功能")
        );

        return new CompareResponse(left, right);
    }
}
