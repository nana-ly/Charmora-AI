package com.client.shopguide.adapter;

import android.content.Context;
import android.content.Intent;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageView;
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

        // 占位图
        holder.ivProductImage.setImageResource(R.drawable.ic_placeholder_product);

        holder.tvTitle.setText(product.getTitle());
        holder.tvPrice.setText("¥" + String.format("%.0f", product.getBase_price()));

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

    static class ViewHolder extends RecyclerView.ViewHolder {
        CardView cardProduct;
        ImageView ivProductImage;
        TextView tvTitle;
        TextView tvPrice;
        Button btnAddToCart;

        ViewHolder(@NonNull View itemView) {
            super(itemView);
            cardProduct = itemView.findViewById(R.id.cardProduct);
            ivProductImage = itemView.findViewById(R.id.ivProductImage);
            tvTitle = itemView.findViewById(R.id.tvTitle);
            tvPrice = itemView.findViewById(R.id.tvPrice);
            btnAddToCart = itemView.findViewById(R.id.btnAddToCart);
        }
    }
}
