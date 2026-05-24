package com.client.shopguide.adapter;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
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
                    text = "▌";
                } else if (message.isStreaming()) {
                    text = text + " ▌";
                }
                ((AssistantViewHolder) holder).tvAssistantMessage.setText(text);
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
        if (product == null) {
            return;
        }

        holder.tvTitle.setText(product.getTitle());
        holder.tvBrandCategory.setText(product.getBrand());
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

    static class ProductViewHolder extends RecyclerView.ViewHolder {
        TextView tvTitle;
        TextView tvBrandCategory;
        TextView tvPrice;
        TextView tvReason;
        TextView tvMatchedEvidence;

        ProductViewHolder(@NonNull View itemView) {
            super(itemView);
            tvTitle = itemView.findViewById(R.id.tvTitle);
            tvBrandCategory = itemView.findViewById(R.id.tvBrandCategory);
            tvPrice = itemView.findViewById(R.id.tvPrice);
            tvReason = itemView.findViewById(R.id.tvReason);
            tvMatchedEvidence = itemView.findViewById(R.id.tvMatchedEvidence);
        }
    }
}
