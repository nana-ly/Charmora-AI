package com.client.shopguide;

import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.client.shopguide.model.CartSnapshot;
import com.client.shopguide.model.CheckoutPreview;
import com.client.shopguide.model.OrderSnapshot;
import com.client.shopguide.model.Product;
import com.client.shopguide.model.StoreCategory;
import com.client.shopguide.model.StorePresentation;
import com.client.shopguide.network.BackendApiClient;
import com.client.shopguide.network.BackendConfig;
import com.google.android.material.bottomnavigation.BottomNavigationView;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;

import java.io.IOException;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import coil.Coil;
import coil.request.ImageRequest;

public class StorefrontActivity extends AppCompatActivity {
    private static final String PREFS_NAME = "shopguide_chat";
    private static final String KEY_SESSION_ID = "session_id";

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private BackendApiClient api;
    private LinearLayout content;
    private ProgressBar progress;
    private EditText search;
    private String sessionId;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        RetrofitClient.configure(this);
        setContentView(R.layout.activity_storefront);
        api = new BackendApiClient();
        content = findViewById(R.id.storeContent);
        progress = findViewById(R.id.storeProgress);
        search = findViewById(R.id.etStoreSearch);
        sessionId = ensureSession();
        findViewById(R.id.btnStoreSettings).setOnClickListener(v -> showEndpointDialog());

        findViewById(R.id.btnStoreSearch).setOnClickListener(v -> loadProducts(search.getText().toString(), null, "newest", true));
        search.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEARCH) {
                loadProducts(search.getText().toString(), null, "newest", true);
                return true;
            }
            return false;
        });

        BottomNavigationView nav = findViewById(R.id.storeBottomNav);
        nav.setOnItemSelectedListener(item -> {
            int id = item.getItemId();
            if (id == R.id.nav_home) showHome();
            else if (id == R.id.nav_categories) showCategories();
            else if (id == R.id.nav_ai) openAiTab();
            else if (id == R.id.nav_cart) showCart();
            else if (id == R.id.nav_profile) showOrders();
            return true;
        });
        int requestedTab = getIntent().getIntExtra("selected_tab", R.id.nav_home);
        nav.setSelectedItemId(requestedTab);
        if (requestedTab == R.id.nav_home) showHome();
        checkConnection();
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private String ensureSession() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String value = prefs.getString(KEY_SESSION_ID, null);
        if (value == null || value.isEmpty()) {
            value = UUID.randomUUID().toString();
            prefs.edit().putString(KEY_SESSION_ID, value).apply();
        }
        return value;
    }

    private void showHome() {
        search.setVisibility(View.VISIBLE);
        clearContent();
        TextView banner = text("从灵感到下单，\nAI 陪你选得刚刚好。", 18, Color.WHITE);
        banner.setTypeface(Typeface.DEFAULT_BOLD);
        banner.setPadding(dp(18), dp(22), dp(18), dp(22));
        banner.setBackground(round(0xFFB4A1C8, 18));
        banner.setOnClickListener(v -> openAiTab());
        content.addView(banner, fullMargins(0, 0, 0, 16));
        addSectionTitle("生活方式精选");
        loadProducts("", null, "newest", false);
    }

    private void showCategories() {
        search.setVisibility(View.VISIBLE);
        clearContent();
        addSectionTitle("按品类逛逛");
        loading(true);
        executor.execute(() -> {
            try {
                List<StoreCategory> categories = api.getCategories();
                runOnUiThread(() -> {
                    loading(false);
                    ChipGroup chips = new ChipGroup(this);
                    chips.setSingleSelection(true);
                    for (StoreCategory category : categories) {
                        Chip chip = new Chip(this);
                        chip.setText(category.name + "  " + category.productCount);
                        chip.setCheckable(true);
                        chip.setOnClickListener(v -> loadProducts("", category.id, "newest", true));
                        chips.addView(chip);
                    }
                    content.addView(chips, fullMargins(0, 0, 0, 12));
                    loadProducts("", null, "newest", false);
                });
            } catch (IOException error) {
                showError(error);
            }
        });
    }

    private void loadProducts(String query, String categoryId, String sort, boolean replaceBody) {
        loading(true);
        executor.execute(() -> {
            try {
                List<Product> products = api.getProducts(query, categoryId, sort);
                runOnUiThread(() -> {
                    loading(false);
                    if (replaceBody) {
                        clearContent();
                        addSectionTitle(query == null || query.isEmpty() ? "筛选结果" : "“" + query + "”的结果");
                    }
                    if (products.isEmpty()) {
                        content.addView(text("暂时没有匹配商品，试试放宽关键词或让 AI 帮你选。", 14, 0xFFA38C99));
                        return;
                    }
                    for (int i = 0; i < products.size(); i += 2) {
                        LinearLayout row = new LinearLayout(this);
                        row.setOrientation(LinearLayout.HORIZONTAL);
                        row.addView(productCard(products.get(i)), weightedCard());
                        if (i + 1 < products.size()) row.addView(productCard(products.get(i + 1)), weightedCard());
                        else row.addView(new View(this), weightedCard());
                        content.addView(row);
                    }
                });
            } catch (IOException error) {
                showError(error);
            }
        });
    }

    private View productCard(Product product) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(10), dp(10), dp(10), dp(12));
        card.setBackground(round(0xFFFFFDFD, 14));
        ImageView image = new ImageView(this);
        image.setScaleType(ImageView.ScaleType.CENTER_CROP);
        card.addView(image, new LinearLayout.LayoutParams(-1, dp(142)));
        Coil.imageLoader(this).enqueue(new ImageRequest.Builder(this)
                .data(product.getImageUrl()).target(image)
                .placeholder(R.drawable.ic_placeholder_product)
                .error(R.drawable.ic_placeholder_product).crossfade(200).build());
        TextView title = text(product.getTitle(), 15, 0xFF6F5967);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setMaxLines(2);
        card.addView(title, fullMargins(0, 10, 0, 4));
        card.addView(text(product.getCategory(), 12, 0xFFA38C99));
        TextView price = text(String.format(Locale.CHINA, "¥%.2f", product.getBase_price()), 18, 0xFFB27790);
        price.setTypeface(Typeface.DEFAULT_BOLD);
        card.addView(price, fullMargins(0, 8, 0, 6));
        Button add = new Button(this);
        add.setText("加入购物车");
        add.setTextColor(Color.WHITE);
        add.setTextSize(12);
        add.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xFFC98FA6));
        add.setOnClickListener(v -> addToCart(product));
        card.addView(add, new LinearLayout.LayoutParams(-1, dp(42)));
        card.setOnClickListener(v -> openProduct(product));
        return card;
    }

    private void addToCart(Product product) {
        executor.execute(() -> {
            try {
                api.addToCart(sessionId, product.getSku_id());
                runOnUiThread(() -> Toast.makeText(this, product.getTitle() + " 已加入购物车", Toast.LENGTH_SHORT).show());
            } catch (IOException error) {
                showError(error);
            }
        });
    }

    private void openProduct(Product product) {
        Intent intent = new Intent(this, ProductDetailActivity.class);
        intent.putExtra("product_id", product.getProduct_id());
        intent.putExtra("sku_id", product.getSku_id());
        intent.putExtra("session_id", sessionId);
        intent.putExtra("title", product.getTitle());
        intent.putExtra("brand", product.getBrand());
        intent.putExtra("price", product.getBase_price());
        intent.putExtra("image_url", product.getImageUrl());
        intent.putExtra("marketing_desc", product.getMarketingDesc());
        intent.putExtra("reason", "来自生活方式商城的在库商品");
        intent.putExtra("evidence", "价格与库存由 ShopGuide 商品真值库提供");
        startActivity(intent);
    }

    private void showCart() {
        search.setVisibility(View.GONE);
        clearContent();
        addSectionTitle("购物车");
        loading(true);
        executor.execute(() -> {
            try {
                CartSnapshot cart = api.getCart(sessionId);
                runOnUiThread(() -> renderCart(cart));
            } catch (IOException error) {
                showError(error);
            }
        });
    }

    private void renderCart(CartSnapshot cart) {
        loading(false);
        while (content.getChildCount() > 1) content.removeViewAt(1);
        if (cart.items.isEmpty()) {
            content.addView(text("购物车还是空的，先去首页挑选商品吧。", 15, 0xFFA38C99));
            return;
        }
        for (CartSnapshot.Item item : cart.items) {
            LinearLayout row = new LinearLayout(this);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(12), dp(10), dp(12), dp(10));
            row.setBackground(round(0xFFFFFDFD, 12));
            LinearLayout info = new LinearLayout(this);
            info.setOrientation(LinearLayout.VERTICAL);
            info.addView(text(item.title, 15, 0xFF6F5967));
            info.addView(text(String.format(Locale.CHINA, "¥%.2f · 库存 %d", item.unitPrice, item.availableQuantity), 13, 0xFFA38C99));
            row.addView(info, new LinearLayout.LayoutParams(0, -2, 1));
            Button minus = smallButton("−");
            Button plus = smallButton("+");
            TextView quantity = text(String.valueOf(item.quantity), 15, 0xFF6F5967);
            quantity.setGravity(Gravity.CENTER);
            minus.setOnClickListener(v -> changeCart(item, item.quantity - 1));
            plus.setOnClickListener(v -> changeCart(item, item.quantity + 1));
            row.addView(minus, new LinearLayout.LayoutParams(dp(42), dp(42)));
            row.addView(quantity, new LinearLayout.LayoutParams(dp(36), dp(42)));
            row.addView(plus, new LinearLayout.LayoutParams(dp(42), dp(42)));
            content.addView(row, fullMargins(0, 0, 0, 10));
        }
        TextView total = text(String.format(Locale.CHINA, "合计  ¥%.2f", cart.totalAmount), 20, 0xFF6F5967);
        total.setTypeface(Typeface.DEFAULT_BOLD);
        total.setGravity(Gravity.END);
        content.addView(total, fullMargins(0, 12, 0, 12));
        Button checkout = primaryButton("去结算（演示支付）");
        checkout.setOnClickListener(v -> beginCheckout());
        content.addView(checkout, new LinearLayout.LayoutParams(-1, dp(50)));
    }

    private void changeCart(CartSnapshot.Item item, int quantity) {
        executor.execute(() -> {
            try {
                if (quantity <= 0) api.removeCartItem(sessionId, item.skuId);
                else api.updateCart(sessionId, item.skuId, quantity);
                runOnUiThread(this::showCart);
            } catch (IOException error) {
                showError(error);
            }
        });
    }

    private void beginCheckout() {
        loading(true);
        executor.execute(() -> {
            try {
                CheckoutPreview preview = api.previewCheckout(sessionId);
                runOnUiThread(() -> showCheckoutDialog(preview));
            } catch (IOException error) {
                showError(error);
            }
        });
    }

    private void showCheckoutDialog(CheckoutPreview preview) {
        loading(false);
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(20), dp(8), dp(20), 0);
        EditText name = field("收货人", "演示用户");
        EditText phone = field("手机号", "13800000000");
        EditText address = field("收货地址", "演示地址：幸福路 1 号");
        EditText note = field("订单备注（选填）", "");
        form.addView(name); form.addView(phone); form.addView(address); form.addView(note);
        RadioGroup payments = new RadioGroup(this);
        payments.setOrientation(RadioGroup.VERTICAL);
        String[] labels = {"微信支付（演示）", "支付宝（演示）", "银行卡（演示）"};
        String[] values = {"demo_wechat", "demo_alipay", "demo_bank_card"};
        for (int i = 0; i < labels.length; i++) {
            RadioButton radio = new RadioButton(this);
            radio.setId(View.generateViewId());
            radio.setText(labels[i]);
            radio.setTag(values[i]);
            payments.addView(radio);
            if (i == 0) payments.check(radio.getId());
        }
        form.addView(payments);
        new AlertDialog.Builder(this)
                .setTitle(String.format(Locale.CHINA, "确认结算 · ¥%.2f", preview.cart.totalAmount))
                .setMessage("价格和库存已复核。此页面仅模拟支付，不会产生真实扣款。")
                .setView(form)
                .setNegativeButton("返回修改", null)
                .setPositiveButton("确认演示支付", (dialog, which) -> {
                    RadioButton selected = payments.findViewById(payments.getCheckedRadioButtonId());
                    submitOrder(preview, name.getText().toString(), phone.getText().toString(),
                            address.getText().toString(), note.getText().toString(), (String) selected.getTag());
                }).show();
    }

    private void submitOrder(CheckoutPreview preview, String name, String phone, String address, String note, String payment) {
        loading(true);
        executor.execute(() -> {
            try {
                OrderSnapshot order = api.createOrder(sessionId, preview, name, phone, address, note, payment);
                runOnUiThread(() -> showOrderSuccess(order));
            } catch (IOException error) {
                showError(error);
            }
        });
    }

    private void showOrderSuccess(OrderSnapshot order) {
        loading(false);
        StringBuilder timeline = new StringBuilder();
        for (OrderSnapshot.Event event : order.statusEvents) timeline.append("\n✓ ").append(event.reason);
        new AlertDialog.Builder(this)
                .setTitle("模拟下单成功")
                .setMessage("订单号：" + order.id + "\n金额：¥" + String.format(Locale.CHINA, "%.2f", order.totalAmount)
                        + "\n状态：" + StorePresentation.statusLabel(order.status) + timeline)
                .setPositiveButton("查看订单", (d, w) -> showOrders())
                .setNegativeButton("继续逛逛", (d, w) -> showHome())
                .show();
    }

    private void showOrders() {
        search.setVisibility(View.GONE);
        clearContent();
        addSectionTitle("我的订单");
        content.addView(text("演示账号 · 不包含真实个人信息和真实支付", 13, 0xFFA38C99), fullMargins(0, 0, 0, 12));
        loading(true);
        executor.execute(() -> {
            try {
                List<OrderSnapshot> orders = api.getOrders(sessionId);
                runOnUiThread(() -> {
                    loading(false);
                    if (orders.isEmpty()) content.addView(text("还没有订单。", 15, 0xFFA38C99));
                    for (OrderSnapshot order : orders) {
                        LinearLayout card = new LinearLayout(this);
                        card.setOrientation(LinearLayout.VERTICAL);
                        card.setPadding(dp(14), dp(12), dp(14), dp(12));
                        card.setBackground(round(0xFFFFFDFD, 12));
                        card.addView(text("订单 " + order.id, 13, 0xFFA38C99));
                        TextView status = text(StorePresentation.statusLabel(order.status), 16, 0xFF6F5967);
                        status.setTypeface(Typeface.DEFAULT_BOLD);
                        card.addView(status, fullMargins(0, 6, 0, 4));
                        card.addView(text(String.format(Locale.CHINA, "¥%.2f · %s", order.totalAmount, StorePresentation.paymentLabel(order.paymentMethod)), 14, 0xFF6F5967));
                        for (OrderSnapshot.Event event : order.statusEvents) card.addView(text("✓ " + event.reason, 13, 0xFFA38C99));
                        content.addView(card, fullMargins(0, 0, 0, 10));
                    }
                });
            } catch (IOException error) {
                showError(error);
            }
        });
    }

    private void clearContent() { content.removeAllViews(); }
    private void loading(boolean visible) { progress.setVisibility(visible ? View.VISIBLE : View.GONE); }
    private void addSectionTitle(String value) {
        TextView title = text(value, 20, 0xFF6F5967);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        content.addView(title, fullMargins(2, 2, 0, 12));
    }
    private void showError(Exception error) {
        runOnUiThread(() -> {
            loading(false);
            Toast.makeText(this, error.getMessage() + "。可在右上角设置服务地址。", Toast.LENGTH_LONG).show();
        });
    }
    private TextView text(String value, int sp, int color) {
        TextView view = new TextView(this); view.setText(value); view.setTextSize(sp); view.setTextColor(color); return view;
    }
    private Button smallButton(String value) { Button b = new Button(this); b.setText(value); b.setTextSize(18); return b; }
    private Button primaryButton(String value) {
        Button button = new Button(this); button.setText(value); button.setTextColor(Color.WHITE);
        button.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xFFC98FA6)); return button;
    }

    private void openAiTab() {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        startActivity(intent);
        overridePendingTransition(0, 0);
    }

    private void checkConnection() {
        TextView status = findViewById(R.id.tvConnectionStatus);
        status.setText("正在检查 · " + BackendConfig.getBaseUrl(this));
        executor.execute(() -> {
            boolean connected = api.healthCheck();
            runOnUiThread(() -> status.setText(connected
                    ? "服务已连接 · 商品与订单可用"
                    : "服务未连接 · 点右侧设置地址"));
        });
    }

    private void showEndpointDialog() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(BackendConfig.getBaseUrl(this));
        input.setSelectAllOnFocus(true);
        int padding = dp(20);
        new AlertDialog.Builder(this)
                .setTitle("后端服务地址")
                .setMessage("模拟器使用 10.0.2.2；真机请填写电脑局域网 IP 或已部署的 HTTPS 地址。")
                .setView(input, padding, dp(8), padding, 0)
                .setNegativeButton("取消", null)
                .setPositiveButton("保存并重连", (dialog, which) -> {
                    BackendConfig.setBaseUrl(this, input.getText().toString());
                    RetrofitClient.configure(this);
                    recreate();
                }).show();
    }
    private EditText field(String hint, String value) {
        EditText field = new EditText(this); field.setHint(hint); field.setText(value); field.setSingleLine(true);
        field.setPadding(dp(10), dp(8), dp(10), dp(8)); return field;
    }
    private GradientDrawable round(int color, int radiusDp) {
        GradientDrawable drawable = new GradientDrawable(); drawable.setColor(color); drawable.setCornerRadius(dp(radiusDp)); return drawable;
    }
    private LinearLayout.LayoutParams fullMargins(int left, int top, int right, int bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(dp(left), dp(top), dp(right), dp(bottom)); return params;
    }
    private LinearLayout.LayoutParams weightedCard() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, -2, 1);
        params.setMargins(dp(5), dp(5), dp(5), dp(5)); return params;
    }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
}
