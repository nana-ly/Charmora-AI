package com.client.shopguide.adapter;

import android.content.Context;
import android.content.Intent;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.cardview.widget.CardView;
import androidx.recyclerview.widget.RecyclerView;

import com.client.shopguide.ProductDetailActivity;
import com.client.shopguide.R;
import com.client.shopguide.model.Product;

import java.util.List;

public class ProductCardAdapter extends RecyclerView.Adapter<ProductCardAdapter.ViewHolder> {

    private List<Product> products;

    public ProductCardAdapter(List<Product> products) {
        this.products = products;
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_product_card, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        Product product = products.get(position);

        // 占位图（TODO: 等后端返回真实 imageUrl 后，用 Coil 加载）
        holder.ivProductImage.setImageResource(R.drawable.ic_placeholder_product);

        holder.tvTitle.setText(product.getTitle());
        holder.tvPrice.setText("¥" + String.format("%.0f", product.getBase_price()));

        // 品牌信息
        String brand = product.getBrand();
        if (brand != null && !brand.isEmpty()) {
            holder.tvBrand.setText(brand);
            holder.tvBrand.setVisibility(View.VISIBLE);
        } else {
            holder.tvBrand.setVisibility(View.GONE);
        }

        // 评分（TODO: 等后端返回真实 rating 后显示）
        float rating = product.getRating();
        if (rating > 0) {
            holder.tvRating.setText("★ " + String.format("%.1f", rating));
            holder.tvRating.setVisibility(View.VISIBLE);
        } else {
            holder.tvRating.setVisibility(View.GONE);
        }

        // 销量（TODO: 等后端返回真实 soldCount 后显示）
        int soldCount = product.getSoldCount();
        if (soldCount > 0) {
            holder.tvSoldCount.setText("已售 " + formatSoldCount(soldCount));
            holder.tvSoldCount.setVisibility(View.VISIBLE);
        } else {
            holder.tvSoldCount.setVisibility(View.GONE);
        }

        // 标签（TODO: 等后端返回真实 tags 后显示）
        List<String> tags = product.getTags();
        holder.llTags.removeAllViews();
        if (tags != null && !tags.isEmpty()) {
            holder.llTags.setVisibility(View.VISIBLE);
            for (String tag : tags) {
                TextView tagView = new TextView(holder.llTags.getContext());
                tagView.setText(tag);
                tagView.setTextSize(10);
                tagView.setTextColor(0xFFFF5722);
                tagView.setBackgroundResource(R.drawable.bg_tag);
                tagView.setPadding(6, 2, 6, 2);
                LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT);
                params.setMargins(0, 0, 4, 0);
                holder.llTags.addView(tagView, params);
            }
        } else {
            holder.llTags.setVisibility(View.GONE);
        }

        // 点击 → 详情页
        holder.cardProduct.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Context context = v.getContext();
                Intent intent = new Intent(context, ProductDetailActivity.class);
                intent.putExtra("product_id", product.getProduct_id());
                intent.putExtra("title", product.getTitle());
                intent.putExtra("brand", product.getBrand());
                intent.putExtra("price", product.getBase_price());
                intent.putExtra("reason", product.getReason());
                intent.putExtra("evidence", product.getMatched_evidence());
                context.startActivity(intent);
            }
        });

        // 加入购物车
        holder.btnAddToCart.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Toast.makeText(v.getContext(),
                        product.getTitle() + " 已加入购物车", Toast.LENGTH_SHORT).show();
            }
        });
    }

    @Override
    public int getItemCount() {
        return products == null ? 0 : products.size();
    }

    /**
     * 格式化销量数字，如 1234 → "1234"，11234 → "1.1万"
     */
    private String formatSoldCount(int count) {
        if (count >= 10000) {
            return String.format("%.1f万", count / 10000.0);
        }
        return String.valueOf(count);
    }

    static class ViewHolder extends RecyclerView.ViewHolder {
        CardView cardProduct;
        ImageView ivProductImage;
        TextView tvTitle;
        TextView tvPrice;
        TextView tvBrand;
        TextView tvRating;
        TextView tvSoldCount;
        LinearLayout llTags;
        Button btnAddToCart;

        ViewHolder(@NonNull View itemView) {
            super(itemView);
            cardProduct = itemView.findViewById(R.id.cardProduct);
            ivProductImage = itemView.findViewById(R.id.ivProductImage);
            tvTitle = itemView.findViewById(R.id.tvTitle);
            tvPrice = itemView.findViewById(R.id.tvPrice);
            tvBrand = itemView.findViewById(R.id.tvBrand);
            tvRating = itemView.findViewById(R.id.tvRating);
            tvSoldCount = itemView.findViewById(R.id.tvSoldCount);
            llTags = itemView.findViewById(R.id.llTags);
            btnAddToCart = itemView.findViewById(R.id.btnAddToCart);
        }
    }
}
