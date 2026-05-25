package com.client.shopguide.adapter;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.client.shopguide.R;
import com.client.shopguide.model.ChatUiMessage;
import com.client.shopguide.model.Product;

import java.util.List;

public class ChatAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> {

    private List<ChatUiMessage> messages;

    public ChatAdapter(List<ChatUiMessage> messages) {
        this.messages = messages;
    }

    public void setMessages(List<ChatUiMessage> messages) {
        this.messages = messages;
        notifyDataSetChanged();
    }

    @Override
    public int getItemViewType(int position) {
        return messages.get(position).getType();
    }

    @NonNull
    @Override
    public RecyclerView.ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        LayoutInflater inflater = LayoutInflater.from(parent.getContext());
        switch (viewType) {
            case ChatUiMessage.TYPE_USER:
                return new UserViewHolder(inflater.inflate(R.layout.item_chat_user, parent, false));
            case ChatUiMessage.TYPE_ASSISTANT:
                return new AssistantViewHolder(inflater.inflate(R.layout.item_chat_assistant, parent, false));
            case ChatUiMessage.TYPE_PRODUCT_ROW:
                return new ProductRowViewHolder(inflater.inflate(R.layout.item_chat_product_row, parent, false));
            case ChatUiMessage.TYPE_PRODUCT:
                return new ProductViewHolder(inflater.inflate(R.layout.item_product, parent, false));
            case ChatUiMessage.TYPE_LOADING:
            default:
                return new LoadingViewHolder(inflater.inflate(R.layout.item_chat_loading, parent, false));
        }
    }

    @Override
    public void onBindViewHolder(@NonNull RecyclerView.ViewHolder holder, int position) {
        ChatUiMessage message = messages.get(position);
        switch (message.getType()) {
            case ChatUiMessage.TYPE_USER:
                ((UserViewHolder) holder).tvUserMessage.setText(message.getContent());
                break;
            case ChatUiMessage.TYPE_ASSISTANT:
                String text = message.getContent();
                if (message.isStreaming() && (text == null || text.isEmpty())) {
                    text = "\u258C";
                } else if (message.isStreaming()) {
                    text = text + " \u258C";
                }
                ((AssistantViewHolder) holder).tvAssistantMessage.setText(text);
                break;
            case ChatUiMessage.TYPE_PRODUCT_ROW:
                List<Product> products = message.getProductList();
                if (products != null && !products.isEmpty()) {
                    ProductCardAdapter cardAdapter = new ProductCardAdapter(products);
                    ((ProductRowViewHolder) holder).rvProductRow.setAdapter(cardAdapter);
                }
                break;
            case ChatUiMessage.TYPE_PRODUCT:
                bindProduct((ProductViewHolder) holder, message.getProduct());
                break;
            case ChatUiMessage.TYPE_LOADING:
                ((LoadingViewHolder) holder).tvLoadingMessage.setText(message.getContent());
                break;
            default:
                break;
        }
    }

    private void bindProduct(ProductViewHolder holder, Product product) {
        if (product == null) return;
        holder.ivProductImage.setImageResource(R.drawable.ic_placeholder_product);
        holder.tvTitle.setText(product.getTitle());
        holder.tvPrice.setText("¥" + String.format("%.0f", product.getBase_price()));
        holder.btnAddToCart.setOnClickListener(v -> {
            android.widget.Toast.makeText(v.getContext(),
                    product.getTitle() + " 已加入购物车",
                    android.widget.Toast.LENGTH_SHORT).show();
        });
    }

    @Override
    public int getItemCount() {
        return messages == null ? 0 : messages.size();
    }

    static class UserViewHolder extends RecyclerView.ViewHolder {
        TextView tvUserMessage;
        UserViewHolder(@NonNull View itemView) {
            super(itemView);
            tvUserMessage = itemView.findViewById(R.id.tvUserMessage);
        }
    }

    static class AssistantViewHolder extends RecyclerView.ViewHolder {
        TextView tvAssistantMessage;
        AssistantViewHolder(@NonNull View itemView) {
            super(itemView);
            tvAssistantMessage = itemView.findViewById(R.id.tvAssistantMessage);
        }
    }

    static class LoadingViewHolder extends RecyclerView.ViewHolder {
        TextView tvLoadingMessage;
        LoadingViewHolder(@NonNull View itemView) {
            super(itemView);
            tvLoadingMessage = itemView.findViewById(R.id.tvLoadingMessage);
        }
    }

    static class ProductRowViewHolder extends RecyclerView.ViewHolder {
        RecyclerView rvProductRow;
        ProductRowViewHolder(@NonNull View itemView) {
            super(itemView);
            rvProductRow = itemView.findViewById(R.id.rvProductRow);
            rvProductRow.setLayoutManager(
                    new LinearLayoutManager(itemView.getContext(),
                            LinearLayoutManager.HORIZONTAL, false));
        }
    }

    static class ProductViewHolder extends RecyclerView.ViewHolder {
        ImageView ivProductImage;
        TextView tvTitle;
        TextView tvPrice;
        Button btnAddToCart;

        ProductViewHolder(@NonNull View itemView) {
            super(itemView);
            ivProductImage = itemView.findViewById(R.id.ivProductImage);
            tvTitle = itemView.findViewById(R.id.tvTitle);
            tvPrice = itemView.findViewById(R.id.tvPrice);
            btnAddToCart = itemView.findViewById(R.id.btnAddToCart);
        }
    }
}
