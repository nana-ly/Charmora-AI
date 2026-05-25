package com.client.shopguide.adapter;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.client.shopguide.R;
import com.client.shopguide.model.Product;

import java.util.List;

public class ProductAdapter extends RecyclerView.Adapter<ProductAdapter.ViewHolder> {

    private List<Product> productList;

    public ProductAdapter(List<Product> productList) {
        this.productList = productList;
    }

    public void updateData(List<Product> newList) {
        this.productList = newList;
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_product, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        Product product = productList.get(position);

        holder.ivProductImage.setImageResource(R.drawable.ic_placeholder_product);
        holder.tvTitle.setText(product.getTitle());
        holder.tvPrice.setText("¥" + String.format("%.0f", product.getBase_price()));
    }

    @Override
    public int getItemCount() {
        return productList == null ? 0 : productList.size();
    }

    static class ViewHolder extends RecyclerView.ViewHolder {

        ImageView ivProductImage;
        TextView tvTitle;
        TextView tvPrice;

        ViewHolder(@NonNull View itemView) {
            super(itemView);
            ivProductImage = itemView.findViewById(R.id.ivProductImage);
            tvTitle = itemView.findViewById(R.id.tvTitle);
            tvPrice = itemView.findViewById(R.id.tvPrice);
        }
    }
}
