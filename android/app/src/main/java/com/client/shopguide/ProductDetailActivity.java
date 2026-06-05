package com.client.shopguide;

import android.os.Bundle;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import coil.Coil;
import coil.request.ImageRequest;
import com.client.shopguide.model.FaqItem;
import com.client.shopguide.model.ReviewItem;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;

import java.util.List;

public class ProductDetailActivity extends AppCompatActivity {

    private static final String IMAGE_BASE_URL = "http://10.0.2.2:8000/static/";

    private ImageView ivProductImage;
    private TextView tvTitle, tvBrand, tvPrice, tvReason, tvEvidence;
    private TextView tvRating, tvSold, tvMarketingDesc;
    private LinearLayout llReviews, llFaqs;

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
        tvRating = findViewById(R.id.tvDetailRating);
        tvSold = findViewById(R.id.tvDetailSold);
        tvMarketingDesc = findViewById(R.id.tvDetailMarketing);
        llReviews = findViewById(R.id.llReviews);
        llFaqs = findViewById(R.id.llFaqs);

        // 从 Intent 读取数据
        String title = getIntent().getStringExtra("title");
        String brand = getIntent().getStringExtra("brand");
        double price = getIntent().getDoubleExtra("price", 0);
        String priceRange = getIntent().getStringExtra("price_range");
        String reason = getIntent().getStringExtra("reason");
        String evidence = getIntent().getStringExtra("evidence");
        String imageUrl = getIntent().getStringExtra("image_url");
        float rating = getIntent().getFloatExtra("rating", 0);
        int soldCount = getIntent().getIntExtra("sold_count", 0);
        int reviewCount = getIntent().getIntExtra("review_count", 0);
        String marketingDesc = getIntent().getStringExtra("marketing_desc");
        String reviewsJson = getIntent().getStringExtra("reviews_json");
        String faqsJson = getIntent().getStringExtra("faqs_json");

        // 用 Coil 加载商品大图
        String fullUrl = (imageUrl != null && !imageUrl.isEmpty())
                ? IMAGE_BASE_URL + imageUrl : null;
        ImageRequest imgReq = new ImageRequest.Builder(this)
                .data(fullUrl)
                .target(ivProductImage)
                .placeholder(R.drawable.ic_placeholder_product)
                .error(R.drawable.ic_placeholder_product)
                .crossfade(300)
                .build();
        Coil.imageLoader(this).enqueue(imgReq);

        tvTitle.setText(title != null ? title : "");
        tvBrand.setText(brand != null ? brand : "");
        tvPrice.setText(priceRange != null && !priceRange.isEmpty()
                ? priceRange : "¥" + String.format("%.0f", price));

        if (rating > 0) tvRating.setText("★ " + String.format("%.1f", rating));
        else tvRating.setVisibility(View.GONE);

        StringBuilder soldText = new StringBuilder();
        if (soldCount > 0) soldText.append("已售 ").append(soldCount >= 10000
                ? String.format("%.1f万", soldCount / 10000.0) : String.valueOf(soldCount));
        if (reviewCount > 0) soldText.append(" · ").append(reviewCount).append("条评论");
        if (soldText.length() > 0) tvSold.setText(soldText);
        else tvSold.setVisibility(View.GONE);

        tvReason.setText(reason != null ? reason : "暂无推荐理由");
        tvEvidence.setText(evidence != null ? evidence : "");
        // 匹配依据：默认1行折叠，点击展开
        if (evidence != null && !evidence.isEmpty()) {
            tvEvidence.setMaxLines(1);
            tvEvidence.setEllipsize(android.text.TextUtils.TruncateAt.END);
            final boolean[] evidenceExpanded = {false};
            tvEvidence.setOnClickListener(v -> {
                if (evidenceExpanded[0]) {
                    tvEvidence.setMaxLines(1);
                    tvEvidence.setEllipsize(android.text.TextUtils.TruncateAt.END);
                } else {
                    tvEvidence.setMaxLines(Integer.MAX_VALUE);
                    tvEvidence.setEllipsize(null);
                }
                evidenceExpanded[0] = !evidenceExpanded[0];
            });
        }

        // 商品介绍（默认3行折叠）
        if (marketingDesc != null && !marketingDesc.isEmpty()) {
            tvMarketingDesc.setText(marketingDesc);
            tvMarketingDesc.setMaxLines(3);
            tvMarketingDesc.setEllipsize(android.text.TextUtils.TruncateAt.END);
            final boolean[] descExpanded = {false};
            tvMarketingDesc.setOnClickListener(v -> {
                if (descExpanded[0]) {
                    tvMarketingDesc.setMaxLines(3);
                    tvMarketingDesc.setEllipsize(android.text.TextUtils.TruncateAt.END);
                } else {
                    tvMarketingDesc.setMaxLines(Integer.MAX_VALUE);
                    tvMarketingDesc.setEllipsize(null);
                }
                descExpanded[0] = !descExpanded[0];
            });
        } else {
            tvMarketingDesc.setVisibility(View.GONE);
        }

        // 用户评论（默认3条折叠）
        Gson gson = new Gson();
        buildReviews(reviewsJson, gson);

        // FAQ（手风琴折叠）
        buildFaqs(faqsJson, gson);

        // 返回按钮
        findViewById(R.id.btnBack).setOnClickListener(v -> finish());

        // 加入购物车
        findViewById(R.id.btnAddToCart).setOnClickListener(v ->
                Toast.makeText(this, title + " 已加入购物车", Toast.LENGTH_SHORT).show());
    }

    // ========== 评论：默认折叠前3条，点「查看更多」展开全部 ==========

    private void buildReviews(String reviewsJson, Gson gson) {
        if (reviewsJson == null || reviewsJson.isEmpty()) return;
        List<ReviewItem> reviews = gson.fromJson(reviewsJson,
                new TypeToken<List<ReviewItem>>() {}.getType());
        if (reviews.isEmpty()) return;

        // 标题加条数
        ((TextView) findViewById(R.id.tvLabelReviews))
                .setText("用户评价(" + reviews.size() + ")");

        int showCount = Math.min(3, reviews.size());
        for (int i = 0; i < showCount; i++) {
            addReviewView(reviews.get(i));
        }

        // 存储全部评论和当前展开状态
        final boolean[] expanded = {false};
        final List<ReviewItem> allReviews = reviews;

        if (reviews.size() > 3) {
            TextView btnMore = new TextView(this);
            btnMore.setText("查看全部 " + reviews.size() + " 条评论 ▼");
            btnMore.setTextSize(13);
            btnMore.setTextColor(0xFF673AB7);
            btnMore.setPadding(0, 8, 0, 4);
            btnMore.setOnClickListener(v -> {
                if (expanded[0]) {
                    // 收起：清空并重建前3条
                    llReviews.removeAllViews();
                    for (int i = 0; i < Math.min(3, allReviews.size()); i++) {
                        addReviewView(allReviews.get(i));
                    }
                    btnMore.setText("查看全部 " + allReviews.size() + " 条评论 ▼");
                } else {
                    // 展开全部
                    llReviews.removeAllViews();
                    for (ReviewItem rv : allReviews) {
                        addReviewView(rv);
                    }
                    btnMore.setText("收起 ▲");
                }
                expanded[0] = !expanded[0];
                // 重新把按钮加回底部
                llReviews.addView(btnMore);
            });
            llReviews.addView(btnMore);
        }
    }

    private void addReviewView(ReviewItem rv) {
        String fullContent = rv.getContent();

        // 头行：头像 + 用户名 ... 评分
        LinearLayout headerRow = new LinearLayout(this);
        headerRow.setOrientation(LinearLayout.HORIZONTAL);
        headerRow.setGravity(android.view.Gravity.CENTER_VERTICAL);
        headerRow.setPadding(0, 6, 0, 4);

        // 头像占位（彩色圆 + 首字）
        String firstChar = rv.getNickname().isEmpty() ? "?" : rv.getNickname().substring(0, 1);
        int[] colors = {0xFF4CAF50, 0xFF2196F3, 0xFFFF9800, 0xFFE91E63, 0xFF9C27B0};
        int avatarColor = colors[Math.abs(rv.getNickname().hashCode()) % colors.length];

        TextView avatar = new TextView(this);
        avatar.setText(firstChar);
        avatar.setTextSize(13);
        avatar.setTextColor(0xFFFFFFFF);
        avatar.setGravity(android.view.Gravity.CENTER);
        LinearLayout.LayoutParams avp = new LinearLayout.LayoutParams(36, 36);
        avp.setMargins(0, 0, 10, 0);
        avatar.setLayoutParams(avp);

        android.graphics.drawable.GradientDrawable avBg = new android.graphics.drawable.GradientDrawable();
        avBg.setShape(android.graphics.drawable.GradientDrawable.OVAL);
        avBg.setColor(avatarColor);
        avatar.setBackground(avBg);

        headerRow.addView(avatar);

        // 用户名
        TextView nameTv = new TextView(this);
        nameTv.setText(rv.getNickname());
        nameTv.setTextSize(13);
        nameTv.setTextColor(0xFF666666);
        headerRow.addView(nameTv);

        // 弹簧占满中间
        View spacer = new View(this);
        spacer.setLayoutParams(new LinearLayout.LayoutParams(0, 0, 1));
        headerRow.addView(spacer);

        // 评分
        TextView ratingTv = new TextView(this);
        ratingTv.setText("★ " + rv.getRating());
        ratingTv.setTextSize(12);
        ratingTv.setTextColor(0xFFFF9800);
        headerRow.addView(ratingTv);

        llReviews.addView(headerRow);

        // 内容行：默认截断2行，可展开
        TextView contentTv = new TextView(this);
        contentTv.setText(fullContent);
        contentTv.setTextSize(13);
        contentTv.setTextColor(0xFF333333);
        contentTv.setMaxLines(2);
        contentTv.setEllipsize(android.text.TextUtils.TruncateAt.END);
        contentTv.setPadding(0, 0, 0, 2);
        llReviews.addView(contentTv);

        // 展开/收起按钮
        TextView toggleTv = new TextView(this);
        toggleTv.setText("展开全文 ▼");
        toggleTv.setTextSize(11);
        toggleTv.setTextColor(0xFF673AB7);
        toggleTv.setPadding(0, 0, 0, 6);
        toggleTv.setOnClickListener(v -> {
            if (contentTv.getMaxLines() == 2) {
                contentTv.setMaxLines(Integer.MAX_VALUE);
                contentTv.setEllipsize(null);
                toggleTv.setText("收起 ▲");
            } else {
                contentTv.setMaxLines(2);
                contentTv.setEllipsize(android.text.TextUtils.TruncateAt.END);
                toggleTv.setText("展开全文 ▼");
            }
        });
        llReviews.addView(toggleTv);

        // 分割线
        View divider = new View(this);
        divider.setLayoutParams(new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 1));
        divider.setBackgroundColor(0xFFEEEEEE);
        llReviews.addView(divider);
    }

    // ========== FAQ：手风琴折叠 ==========

    private void buildFaqs(String faqsJson, Gson gson) {
        if (faqsJson == null || faqsJson.isEmpty()) return;
        List<FaqItem> faqs = gson.fromJson(faqsJson,
                new TypeToken<List<FaqItem>>() {}.getType());

        // 标题加条数
        ((TextView) findViewById(R.id.tvLabelFaqs))
                .setText("常见问题(" + faqs.size() + ")");
        for (FaqItem fq : faqs) {
            // 问题行
            TextView qTv = new TextView(this);
            qTv.setText("▼ Q: " + fq.getQuestion());
            qTv.setTextSize(13);
            qTv.setTextColor(0xFF333333);
            qTv.setTypeface(null, android.graphics.Typeface.BOLD);
            qTv.setPadding(0, 8, 0, 4);
            qTv.setCompoundDrawablePadding(8);
            llFaqs.addView(qTv);

            // 答案
            TextView aTv = new TextView(this);
            aTv.setText(fq.getAnswer());
            aTv.setTextSize(13);
            aTv.setTextColor(0xFF666666);
            aTv.setPadding(0, 0, 0, 8);
            aTv.setVisibility(View.GONE);
            llFaqs.addView(aTv);

            qTv.setOnClickListener(v -> {
                if (aTv.getVisibility() == View.GONE) {
                    aTv.setVisibility(View.VISIBLE);
                    qTv.setText("▲ Q: " + fq.getQuestion());
                } else {
                    aTv.setVisibility(View.GONE);
                    qTv.setText("▼ Q: " + fq.getQuestion());
                }
            });
        }
    }
}
