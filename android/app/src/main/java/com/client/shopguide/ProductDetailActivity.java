package com.client.shopguide;

import android.os.Bundle;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

public class ProductDetailActivity extends AppCompatActivity {

    private ImageView ivProductImage;
    private TextView tvTitle;
    private TextView tvBrand;
    private TextView tvPrice;
    private TextView tvReason;
    private TextView tvEvidence;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_product_detail);

        ivProductImage = findViewById(R.id.ivDetailImage);
        tvTitle = findViewById(R.id.tvDetailTitle);
        tvBrand = findViewById(R.id.tvDetailBrand);
        tvPrice = findViewById(R.id.tvDetailPrice);
        tvReason = findViewById(R.id.tvDetailReason);
        tvEvidence = findViewById(R.id.tvDetailEvidence);

        // 从 Intent 读取数据
        String title = getIntent().getStringExtra("title");
        String brand = getIntent().getStringExtra("brand");
        double price = getIntent().getDoubleExtra("price", 0);
        String reason = getIntent().getStringExtra("reason");
        String evidence = getIntent().getStringExtra("evidence");

        // 占位图
        ivProductImage.setImageResource(R.drawable.ic_placeholder_product);

        tvTitle.setText(title != null ? title : "");
        tvBrand.setText(brand != null ? brand : "");
        tvPrice.setText("¥" + String.format("%.0f", price));
        tvReason.setText(reason != null ? reason : "暂无推荐理由");
        tvEvidence.setText(evidence != null ? evidence : "");

        // 返回按钮
        findViewById(R.id.btnBack).setOnClickListener(v -> finish());
    }
}
