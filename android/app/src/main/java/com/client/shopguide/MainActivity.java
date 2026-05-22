package com.client.shopguide;

import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.client.shopguide.adapter.ProductAdapter;
import com.client.shopguide.model.Product;

import java.util.ArrayList;
import java.util.List;

public class MainActivity extends AppCompatActivity {

    EditText etQuery;
    Button btnRecommend;
    RecyclerView rvProducts;
    TextView tvResultTitle;
    TextView tvLoading;

    ProductAdapter adapter;
    List<Product> productList;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        etQuery = findViewById(R.id.etQuery);
        btnRecommend = findViewById(R.id.btnRecommend);
        rvProducts = findViewById(R.id.rvProducts);
        tvResultTitle = findViewById(R.id.tvResultTitle);
        tvLoading = findViewById(R.id.tvLoading);

        productList = new ArrayList<>();
        adapter = new ProductAdapter(productList);

        rvProducts.setLayoutManager(new LinearLayoutManager(this));
        rvProducts.setAdapter(adapter);

        btnRecommend.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String query = etQuery.getText().toString().trim();

                if (query.isEmpty()) {
                    Toast.makeText(MainActivity.this, "请输入需求", Toast.LENGTH_SHORT).show();
                    return;
                }

                // 显示加载状态
                btnRecommend.setEnabled(false);
                btnRecommend.setText("正在推荐...");
                tvLoading.setVisibility(View.VISIBLE);
                tvResultTitle.setVisibility(View.GONE);

                // 模拟网络请求延迟，1.5秒后展示 Mock 数据
                new Handler().postDelayed(new Runnable() {
                    @Override
                    public void run() {
                        loadMockData();
                    }
                }, 1500);
            }
        });
    }

    /**
     * 加载 Mock 数据（Day 1 用，Day 2 会替换为 Retrofit 真实请求）
     */
    private void loadMockData() {
        List<Product> mockProducts = new ArrayList<>();

        mockProducts.add(new Product(
                "p_digital_001",
                "Apple iPhone 17 Pro 6.3英寸 A19 Pro 256GB 全网通旗舰手机",
                "Apple 苹果",
                "数码电子",
                "智能手机",
                8999.0,
                "这款手机搭载 A19 Pro 芯片，适合视频剪辑；摄像头系统支持高质量拍摄，符合你的拍照和创作需求。",
                "A19 Pro芯片、专业视频剪辑、摄像头系统升级"
        ));

        mockProducts.add(new Product(
                "p_digital_002",
                "Samsung Galaxy S25 Ultra 12GB+256GB AI智能影像手机",
                "Samsung 三星",
                "数码电子",
                "智能手机",
                7999.0,
                "2亿像素摄像头，AI影像增强，支持8K视频录制，拍照和视频创作能力出色。",
                "2亿像素、8K视频、AI影像增强"
        ));

        mockProducts.add(new Product(
                "p_digital_003",
                "Xiaomi 15 Pro 骁龙8 Elite 12GB+512GB 专业影像旗舰",
                "Xiaomi 小米",
                "数码电子",
                "智能手机",
                5999.0,
                "徕卡专业影像系统，骁龙8 Elite芯片性能强劲，适合拍照和游戏，性价比高。",
                "徕卡影像、骁龙8 Elite、高性价比"
        ));

        // 更新数据后恢复界面
        adapter.updateData(mockProducts);
        tvResultTitle.setVisibility(View.VISIBLE);
        tvLoading.setVisibility(View.GONE);
        btnRecommend.setEnabled(true);
        btnRecommend.setText("开始推荐");
    }
}
