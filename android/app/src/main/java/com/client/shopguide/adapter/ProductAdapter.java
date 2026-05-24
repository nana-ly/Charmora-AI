package com.client.shopguide.adapter;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

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

        holder.tvTitle.setText(product.getTitle());

        String category = product.getCategory();
        String subCategory = product.getSub_category();
        if (category != null && !category.isEmpty()) {
            holder.tvBrandCategory.setText(product.getBrand() + " | " + category + " / " + subCategory);
        } else {
            holder.tvBrandCategory.setText(product.getBrand());
        }

        holder.tvPrice.setText("¥" + String.format("%.0f", product.getBase_price()));
        holder.tvReason.setText(product.getReason());

        String evidence = product.getMatched_evidence();
        if (evidence != null && !evidence.isEmpty()) {
            holder.tvMatchedEvidence.setText(evidence);
        } else {
            holder.tvMatchedEvidence.setText("");
        }
    }

    @Override
    public int getItemCount() {
        return productList == null ? 0 : productList.size();
    }

    static class ViewHolder extends RecyclerView.ViewHolder {

        TextView tvTitle;
        TextView tvBrandCategory;
        TextView tvPrice;
        TextView tvReason;
        TextView tvMatchedEvidence;

        ViewHolder(@NonNull View itemView) {
            super(itemView);
            tvTitle = itemView.findViewById(R.id.tvTitle);
            tvBrandCategory = itemView.findViewById(R.id.tvBrandCategory);
            tvPrice = itemView.findViewById(R.id.tvPrice);
            tvReason = itemView.findViewById(R.id.tvReason);
            tvMatchedEvidence = itemView.findViewById(R.id.tvMatchedEvidence);
        }
    }
}
