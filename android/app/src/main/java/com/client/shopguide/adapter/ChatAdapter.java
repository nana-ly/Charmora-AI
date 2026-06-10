package com.client.shopguide.adapter;

import android.os.Handler;
import android.os.Looper;
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

import io.noties.markwon.Markwon;

import java.util.List;

public class ChatAdapter extends RecyclerView.Adapter<RecyclerView.ViewHolder> {

    public interface OnTTSListener {
        void onSpeak(String text);
    }

    private List<ChatUiMessage> messages;
    private ProductCardAdapter.OnAddToCartListener onAddToCartListener;
    private OnTTSListener onTTSListener;
    private Markwon markwon;

    public ChatAdapter(List<ChatUiMessage> messages) {
        this.messages = messages;
    }

    /** 延迟初始化 Markwon */
    private Markwon getMarkwon(View anyView) {
        if (markwon == null) {
            markwon = Markwon.create(anyView.getContext());
        }
        return markwon;
    }

    /** 过滤掉 相似度分数、商品id、向量召回id 等无关技术文字 */
    private static String filterClean(String text) {
        if (text == null) return null;
        return text
                .replaceAll("相似度[：:]\\s*[\\d.]+\\s*", "")
                .replaceAll("[\\s(（]?(商品|产品|向量召回|检索)[Ii]?[Dd]?[：:]\\s*\\S+\\s*", "")
                .replaceAll("[\\s(（]?product_?id[：:]\\s*\\S+\\s*", "")
                .replaceAll("[\\s(（]?retriever[_-]?(id|mode|type)[：:]\\s*\\S+\\s*", "")
                .replaceAll("[\\s(（]?score[：:]\\s*[\\d.]+\\s*", "")
                .replaceAll("[\\s(（]?\\(?召回[：:\\s]*\\S+\\)?\\s*", "")
                .replaceAll("p_?[a-z]+_\\d+\\s*", "");  // 如 p_beauty_001 类id
    }

    public void setMessages(List<ChatUiMessage> messages) {
        this.messages = messages;
        notifyDataSetChanged();
    }

    public void setOnAddToCartListener(ProductCardAdapter.OnAddToCartListener listener) {
        this.onAddToCartListener = listener;
    }

    public void setOnTTSListener(OnTTSListener listener) {
        this.onTTSListener = listener;
    }

    private AssistantViewHolder activeTtsHolder;

    public void dismissTts() {
        if (activeTtsHolder != null && activeTtsHolder.tvTtsIcon != null) {
            activeTtsHolder.tvTtsIcon.setVisibility(View.GONE);
            activeTtsHolder = null;
        }
    }

    private void hideActiveTtsIcon() {
        dismissTts();
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
            case ChatUiMessage.TYPE_DIVIDER:
                return new DividerViewHolder(inflater.inflate(R.layout.item_chat_divider, parent, false));
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
                CharSequence styled = message.getStyledContent();
                String text = message.getContent();

                AssistantViewHolder avh = (AssistantViewHolder) holder;
                if (message.isStreaming()) {
                    if (text == null || text.isEmpty()) {
                        avh.tvAssistantMessage.setText("\u258C");
                    } else {
                        avh.tvAssistantMessage.setText(text + " \u258C");
                    }
                } else if (styled != null) {
                    // 对比场景的 SpannableString 排版
                    avh.tvAssistantMessage.setText(styled);
                } else {
                    String filtered = filterClean(text);
                    String md = filtered != null ? filtered : "";
                    getMarkwon(holder.itemView).setMarkdown(avh.tvAssistantMessage, md);
                }
                avh.tvTtsIcon.setVisibility(View.GONE);

                // 长按出现 ▶ 播放按钮
                if (!message.isStreaming() && text != null && !text.isEmpty()) {
                    final String speakText = message.getContent();
                    avh.itemView.setOnLongClickListener(v -> {
                        hideActiveTtsIcon();
                        activeTtsHolder = avh;
                        avh.tvTtsIcon.setVisibility(View.VISIBLE);
                        avh.tvTtsIcon.setOnClickListener(icon -> {
                            if (onTTSListener != null) onTTSListener.onSpeak(speakText);
                        });
                        return true;
                    });
                }
                break;
            case ChatUiMessage.TYPE_PRODUCT_ROW:
                List<Product> products = message.getProductList();
                if (products != null && !products.isEmpty()) {
                    ProductCardAdapter cardAdapter = new ProductCardAdapter(products);
                    cardAdapter.setOnAddToCartListener(onAddToCartListener);
                    ((ProductRowViewHolder) holder).rvProductRow.setAdapter(cardAdapter);
                } else {
                    ((ProductRowViewHolder) holder).rvProductRow.setAdapter(null);
                }
                break;
            case ChatUiMessage.TYPE_PRODUCT:
                bindProduct((ProductViewHolder) holder, message.getProduct());
                break;
            case ChatUiMessage.TYPE_DIVIDER:
                ((DividerViewHolder) holder).tvDividerTime.setText(message.getContent());
                break;
            case ChatUiMessage.TYPE_LOADING:
                bindLoading((LoadingViewHolder) holder);
                break;
            default:
                break;
        }
    }

    @Override
    public void onViewRecycled(@NonNull RecyclerView.ViewHolder holder) {
        // 回收时停止动画，避免 ViewHolder 复用后残留动画回调
        if (holder instanceof LoadingViewHolder) {
            ((LoadingViewHolder) holder).stopAnimation();
        }
        super.onViewRecycled(holder);
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
        TextView tvTtsIcon;
        AssistantViewHolder(@NonNull View itemView) {
            super(itemView);
            tvAssistantMessage = itemView.findViewById(R.id.tvAssistantMessage);
            tvTtsIcon = itemView.findViewById(R.id.tvTtsIcon);
        }
    }

    // ========== Loading 动画：Handler 手动轮播，保证 1→2→3 顺序 ==========

    private void bindLoading(LoadingViewHolder holder) {
        holder.stopAnimation();
        holder.startAnimation();
    }

    static class DividerViewHolder extends RecyclerView.ViewHolder {
        TextView tvDividerTime;
        DividerViewHolder(@NonNull View itemView) {
            super(itemView);
            tvDividerTime = itemView.findViewById(R.id.tvDividerTime);
        }
    }

    static class LoadingViewHolder extends RecyclerView.ViewHolder {
        View dot1, dot2, dot3;
        private final Handler handler = new Handler(Looper.getMainLooper());
        private int currentDot = 0;
        private boolean running = false;

        private final Runnable cycleRunnable = new Runnable() {
            @Override
            public void run() {
                if (!running) return;
                // 三级渐进波浪：距 currentDot 越近越亮
                animateDotByDistance(0);
                animateDotByDistance(1);
                animateDotByDistance(2);
                currentDot = (currentDot + 1) % 3;
                handler.postDelayed(this, 350);
            }
        };

        LoadingViewHolder(@NonNull View itemView) {
            super(itemView);
            dot1 = itemView.findViewById(R.id.dot1);
            dot2 = itemView.findViewById(R.id.dot2);
            dot3 = itemView.findViewById(R.id.dot3);

            // 初始全部 dim
            setDotStatic(dot1, 0.3f, 0.68f);
            setDotStatic(dot2, 0.3f, 0.68f);
            setDotStatic(dot3, 0.3f, 0.68f);
        }

        void startAnimation() {
            if (running) return;
            running = true;
            currentDot = 0;
            cycleRunnable.run();
        }

        void stopAnimation() {
            running = false;
            handler.removeCallbacks(cycleRunnable);
            resetDots();
        }

        /** 计算 dot index 距当前高亮位置的"年龄"，0=当前, 1=上一个, 2=最远 */
        private int distance(int index) {
            return (index - currentDot + 3) % 3;
        }

        /** 根据距离设置三级亮度 + 缩放，200ms 平滑过渡 */
        private void animateDotByDistance(int index) {
            View dot = (index == 0) ? dot1 : (index == 1) ? dot2 : dot3;
            if (dot == null) return;
            dot.animate().cancel();
            int dist = distance(index);
            switch (dist) {
                case 0: // 当前 → 最亮最大
                    dot.animate().alpha(1.0f).scaleX(1.0f).scaleY(1.0f)
                            .setDuration(200).start();
                    break;
                case 1: // 上一个 → 半亮
                    dot.animate().alpha(0.5f).scaleX(0.82f).scaleY(0.82f)
                            .setDuration(200).start();
                    break;
                case 2: // 最远 → 暗淡但仍可见
                    dot.animate().alpha(0.28f).scaleX(0.68f).scaleY(0.68f)
                            .setDuration(200).start();
                    break;
            }
        }

        private void setDotStatic(View dot, float alpha, float scale) {
            if (dot == null) return;
            dot.setAlpha(alpha);
            dot.setScaleX(scale);
            dot.setScaleY(scale);
        }

        private void resetDots() {
            dot1.animate().cancel();
            dot2.animate().cancel();
            dot3.animate().cancel();
            setDotStatic(dot1, 0.3f, 0.68f);
            setDotStatic(dot2, 0.3f, 0.68f);
            setDotStatic(dot3, 0.3f, 0.68f);
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
