package com.client.shopguide.adapter;

import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.client.shopguide.R;
import com.client.shopguide.model.ChatUiMessage;
import com.client.shopguide.model.CompareItem;
import com.client.shopguide.model.CompareResponse;
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
            case ChatUiMessage.TYPE_COMPARE:
                return new CompareViewHolder(inflater.inflate(R.layout.item_chat_compare, parent, false));
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
            case ChatUiMessage.TYPE_COMPARE:
                bindCompare((CompareViewHolder) holder, message.getCompareResponse());
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
        AssistantViewHolder(@NonNull View itemView) {
            super(itemView);
            tvAssistantMessage = itemView.findViewById(R.id.tvAssistantMessage);
        }
    }

    // ========== Loading 动画：Handler 手动轮播，保证 1→2→3 顺序 ==========

    private void bindLoading(LoadingViewHolder holder) {
        holder.stopAnimation();
        holder.startAnimation();
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

    // ========== 对比卡片 ==========

    private void bindCompare(CompareViewHolder holder, CompareResponse data) {
        if (data == null) return;
        CompareItem left = data.getLeftItem();
        CompareItem right = data.getRightItem();

        if (left != null) {
            holder.tvLeftName.setText(left.getName() != null ? left.getName() : "");
            holder.tvLeftPrice.setText(left.getPrice() != null ? left.getPrice() : "");
            addBulletItems(holder.llLeftPros, left.getPros(), true);
            addBulletItems(holder.llLeftCons, left.getCons(), false);
        }
        if (right != null) {
            holder.tvRightName.setText(right.getName() != null ? right.getName() : "");
            holder.tvRightPrice.setText(right.getPrice() != null ? right.getPrice() : "");
            addBulletItems(holder.llRightPros, right.getPros(), true);
            addBulletItems(holder.llRightCons, right.getCons(), false);
        }
    }

    private void addBulletItems(LinearLayout container, List<String> items, boolean isPros) {
        if (items == null || items.isEmpty()) return;
        for (String item : items) {
            TextView tv = new TextView(container.getContext());
            tv.setText("• " + item);
            tv.setTextSize(11);
            tv.setTextColor(isPros ? 0xFF4CAF50 : 0xFFF44336);
            tv.setPadding(0, 2, 0, 2);
            container.addView(tv);
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

    static class CompareViewHolder extends RecyclerView.ViewHolder {
        TextView tvLeftName, tvLeftPrice, tvRightName, tvRightPrice;
        LinearLayout llLeftPros, llLeftCons, llRightPros, llRightCons;

        CompareViewHolder(@NonNull View itemView) {
            super(itemView);
            tvLeftName = itemView.findViewById(R.id.tvLeftName);
            tvLeftPrice = itemView.findViewById(R.id.tvLeftPrice);
            tvRightName = itemView.findViewById(R.id.tvRightName);
            tvRightPrice = itemView.findViewById(R.id.tvRightPrice);
            llLeftPros = itemView.findViewById(R.id.llLeftPros);
            llLeftCons = itemView.findViewById(R.id.llLeftCons);
            llRightPros = itemView.findViewById(R.id.llRightPros);
            llRightCons = itemView.findViewById(R.id.llRightCons);
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
