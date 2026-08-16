package com.client.shopguide.network;

import com.client.shopguide.RetrofitClient;
import com.client.shopguide.model.Product;
import com.client.shopguide.model.CartSnapshot;
import com.client.shopguide.model.CheckoutPreview;
import com.client.shopguide.model.OrderSnapshot;
import com.client.shopguide.model.StoreCategory;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.FieldNamingPolicy;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

/** Backend-owned multimodal and commerce calls. No long-lived provider credential is in the APK. */
public class BackendApiClient {
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    private final OkHttpClient client = RetrofitClient.getInstance().getOkHttpClient();
    private final String baseUrl = RetrofitClient.getInstance().getBaseUrl();
    private final Gson gson = new GsonBuilder()
            .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
            .create();

    public String absoluteUrl(String value) {
        if (value == null || value.isEmpty() || value.startsWith("http://") || value.startsWith("https://")) {
            return value;
        }
        String origin = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        return value.startsWith("/") ? origin + value : origin + "/" + value;
    }

    public List<StoreCategory> getCategories() throws IOException {
        JsonObject json = executeJson(new Request.Builder().url(baseUrl + "categories").get().build());
        List<StoreCategory> result = new ArrayList<>();
        for (JsonElement element : json.getAsJsonArray("items")) {
            JsonObject item = element.getAsJsonObject();
            StoreCategory category = new StoreCategory();
            category.id = stringValue(item, "id");
            category.name = stringValue(item, "name");
            category.productCount = item.has("product_count") ? item.get("product_count").getAsInt() : 0;
            result.add(category);
        }
        return result;
    }

    public boolean healthCheck() {
        try {
            JsonObject json = executeJson(new Request.Builder().url(baseUrl + "health").get().build());
            return "ok".equals(stringValue(json, "status"));
        } catch (IOException error) {
            return false;
        }
    }

    public List<Product> getProducts(String query, String categoryId, String sort) throws IOException {
        StringBuilder url = new StringBuilder(baseUrl).append("products?limit=60&in_stock=true&sort=").append(sort);
        if (query != null && !query.trim().isEmpty()) {
            url.append("&query=").append(URLEncoder.encode(query.trim(), StandardCharsets.UTF_8));
        }
        if (categoryId != null && !categoryId.isEmpty()) url.append("&category_id=").append(categoryId);
        JsonObject json = executeJson(new Request.Builder().url(url.toString()).get().build());
        List<Product> products = new ArrayList<>();
        for (JsonElement element : json.getAsJsonArray("items")) {
            JsonObject item = element.getAsJsonObject();
            Product product = new Product();
            product.setProduct_id(stringValue(item, "id"));
            product.setTitle(stringValue(item, "title"));
            product.setBrand(stringValue(item, "brand"));
            product.setCategory(stringValue(item, "category_name"));
            product.setMarketingDesc(stringValue(item, "description"));
            JsonArray images = item.getAsJsonArray("images");
            if (images != null && images.size() > 0) product.setImageUrl(absoluteUrl(images.get(0).getAsString()));
            JsonArray skus = item.getAsJsonArray("skus");
            if (skus != null && skus.size() > 0) {
                JsonObject sku = skus.get(0).getAsJsonObject();
                product.setSku_id(stringValue(sku, "id"));
                if (sku.has("price") && !sku.get("price").isJsonNull()) product.setBase_price(sku.get("price").getAsDouble());
            }
            products.add(product);
        }
        return products;
    }

    public CartSnapshot getCart(String sessionId) throws IOException {
        JsonObject json = executeJson(new Request.Builder().url(baseUrl + "cart/" + sessionId).get().build());
        return parseCart(json);
    }

    public CartSnapshot updateCart(String sessionId, String skuId, int quantity) throws IOException {
        JsonObject payload = new JsonObject();
        payload.addProperty("quantity", quantity);
        JsonObject json = executeJson(new Request.Builder().url(baseUrl + "cart/" + sessionId + "/items/" + skuId)
                .patch(RequestBody.create(payload.toString(), JSON)).build());
        return parseCart(json);
    }

    public CartSnapshot removeCartItem(String sessionId, String skuId) throws IOException {
        JsonObject json = executeJson(new Request.Builder().url(baseUrl + "cart/" + sessionId + "/items/" + skuId)
                .delete().build());
        return parseCart(json);
    }

    public CheckoutPreview previewCheckout(String sessionId) throws IOException {
        JsonObject payload = new JsonObject();
        payload.addProperty("session_id", sessionId);
        JsonObject json = executeJson(new Request.Builder().url(baseUrl + "orders/preview")
                .post(RequestBody.create(payload.toString(), JSON)).build());
        CheckoutPreview preview = new CheckoutPreview();
        preview.confirmationToken = stringValue(json, "confirmation_token");
        preview.expiresAt = stringValue(json, "expires_at");
        preview.cart = parseCart(json);
        return preview;
    }

    public OrderSnapshot createOrder(String sessionId, CheckoutPreview preview, String name,
                                     String phone, String address, String note, String payment) throws IOException {
        JsonObject payload = new JsonObject();
        payload.addProperty("session_id", sessionId);
        payload.addProperty("confirmation_token", preview.confirmationToken);
        payload.addProperty("idempotency_key", "android-" + sessionId + "-" + preview.confirmationToken);
        payload.addProperty("recipient_name", name);
        payload.addProperty("recipient_phone", phone);
        payload.addProperty("shipping_address", address);
        payload.addProperty("customer_note", note);
        payload.addProperty("payment_method", payment);
        JsonObject json = executeJson(new Request.Builder().url(baseUrl + "orders")
                .post(RequestBody.create(payload.toString(), JSON)).build());
        return parseOrder(json);
    }

    public List<OrderSnapshot> getOrders(String sessionId) throws IOException {
        JsonObject json = executeJson(new Request.Builder().url(baseUrl + "orders?session_id=" + sessionId + "&limit=50")
                .get().build());
        List<OrderSnapshot> orders = new ArrayList<>();
        for (JsonElement item : json.getAsJsonArray("items")) orders.add(parseOrder(item.getAsJsonObject()));
        return orders;
    }

    private CartSnapshot parseCart(JsonObject json) {
        CartSnapshot cart = new CartSnapshot();
        cart.sessionId = stringValue(json, "session_id");
        cart.totalAmount = json.has("total_amount") ? json.get("total_amount").getAsDouble() : 0;
        JsonArray items = json.has("items") ? json.getAsJsonArray("items") : new JsonArray();
        for (JsonElement element : items) {
            JsonObject value = element.getAsJsonObject();
            CartSnapshot.Item item = new CartSnapshot.Item();
            item.skuId = stringValue(value, "sku_id");
            item.productId = stringValue(value, "product_id");
            item.title = stringValue(value, "title");
            item.skuName = stringValue(value, "sku_name");
            item.quantity = value.get("quantity").getAsInt();
            item.availableQuantity = value.get("available_quantity").getAsInt();
            item.unitPrice = value.get("unit_price").getAsDouble();
            item.imageUrl = absoluteUrl(stringValue(value, "image_url"));
            cart.items.add(item);
        }
        return cart;
    }

    private OrderSnapshot parseOrder(JsonObject json) {
        return gson.fromJson(json, OrderSnapshot.class);
    }

    public String transcribePcm(byte[] pcm) throws IOException {
        byte[] wav = wavFromPcm(pcm, 16000, 1, 16);
        RequestBody file = RequestBody.create(wav, MediaType.get("audio/wav"));
        MultipartBody body = new MultipartBody.Builder().setType(MultipartBody.FORM)
                .addFormDataPart("file", "recording.wav", file).build();
        JsonObject json = executeJson(new Request.Builder().url(baseUrl + "multimodal/asr").post(body).build());
        return json.has("text") ? json.get("text").getAsString() : null;
    }

    public byte[] synthesize(String text) throws IOException {
        JsonObject payload = new JsonObject();
        payload.addProperty("text", text);
        Request request = new Request.Builder().url(baseUrl + "multimodal/tts")
                .post(RequestBody.create(payload.toString(), JSON)).build();
        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful() || response.body() == null) throw apiError(response);
            return response.body().bytes();
        }
    }

    public String understandImage(byte[] content, String mimeType) throws IOException {
        RequestBody file = RequestBody.create(content, MediaType.get(mimeType));
        MultipartBody body = new MultipartBody.Builder().setType(MultipartBody.FORM)
                .addFormDataPart("file", "shopping-image", file).build();
        JsonObject json = executeJson(new Request.Builder()
                .url(baseUrl + "multimodal/images/understand").post(body).build());
        return json.has("description") ? json.get("description").getAsString() : null;
    }

    public List<Product> searchSimilar(byte[] content, String mimeType, int topK) throws IOException {
        RequestBody file = RequestBody.create(content, MediaType.get(mimeType));
        MultipartBody body = new MultipartBody.Builder().setType(MultipartBody.FORM)
                .addFormDataPart("file", "shopping-image", file).build();
        JsonObject json = executeJson(new Request.Builder()
                .url(baseUrl + "multimodal/images/search?top_k=" + topK).post(body).build());
        List<Product> products = new ArrayList<>();
        JsonArray items = json.has("items") ? json.getAsJsonArray("items") : new JsonArray();
        for (JsonElement element : items) {
            JsonObject item = element.getAsJsonObject();
            Product product = new Product();
            product.setProduct_id(stringValue(item, "id"));
            product.setTitle(stringValue(item, "title"));
            product.setBrand(stringValue(item, "brand"));
            product.setMarketingDesc(stringValue(item, "description"));
            if (item.has("images") && item.getAsJsonArray("images").size() > 0) {
                product.setImageUrl(item.getAsJsonArray("images").get(0).getAsString());
            }
            if (item.has("skus") && item.getAsJsonArray("skus").size() > 0) {
                JsonObject sku = item.getAsJsonArray("skus").get(0).getAsJsonObject();
                product.setSku_id(stringValue(sku, "id"));
                if (sku.has("price") && !sku.get("price").isJsonNull()) {
                    product.setBase_price(sku.get("price").getAsDouble());
                }
            }
            product.setReason("图片相似商品");
            product.setMatched_evidence("图像向量召回后经 PostgreSQL 库存与价格校验");
            products.add(product);
        }
        return products;
    }

    public void addToCart(String sessionId, String skuId) throws IOException {
        JsonObject payload = new JsonObject();
        payload.addProperty("sku_id", skuId);
        payload.addProperty("quantity", 1);
        executeJson(new Request.Builder().url(baseUrl + "cart/" + sessionId + "/items")
                .post(RequestBody.create(payload.toString(), JSON)).build());
    }

    public String checkout(String sessionId) throws IOException {
        JsonObject payload = new JsonObject();
        payload.addProperty("session_id", sessionId);
        JsonObject json = executeJson(new Request.Builder().url(baseUrl + "orders")
                .post(RequestBody.create(payload.toString(), JSON)).build());
        return json.has("id") ? json.get("id").getAsString() : null;
    }

    private JsonObject executeJson(Request request) throws IOException {
        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful() || response.body() == null) throw apiError(response);
            return new JsonParser().parse(response.body().string()).getAsJsonObject();
        }
    }

    private IOException apiError(Response response) {
        String message = "服务请求失败：" + response.code();
        try {
            if (response.body() != null) {
                JsonObject body = new JsonParser().parse(response.body().string()).getAsJsonObject();
                if (body.has("message")) message = body.get("message").getAsString();
            }
        } catch (Exception ignored) {}
        return new IOException(message);
    }

    private static String stringValue(JsonObject object, String key) {
        return object.has(key) && !object.get(key).isJsonNull()
                ? object.get(key).getAsString() : "";
    }

    private static byte[] wavFromPcm(byte[] pcm, int sampleRate, int channels, int bits) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream(44 + pcm.length);
        int byteRate = sampleRate * channels * bits / 8;
        writeAscii(out, "RIFF"); writeLe32(out, 36 + pcm.length); writeAscii(out, "WAVEfmt ");
        writeLe32(out, 16); writeLe16(out, 1); writeLe16(out, channels); writeLe32(out, sampleRate);
        writeLe32(out, byteRate); writeLe16(out, channels * bits / 8); writeLe16(out, bits);
        writeAscii(out, "data"); writeLe32(out, pcm.length); out.write(pcm);
        return out.toByteArray();
    }

    private static void writeAscii(ByteArrayOutputStream out, String value) throws IOException { out.write(value.getBytes("US-ASCII")); }
    private static void writeLe16(ByteArrayOutputStream out, int value) { out.write(value & 0xff); out.write((value >> 8) & 0xff); }
    private static void writeLe32(ByteArrayOutputStream out, int value) { writeLe16(out, value); writeLe16(out, value >> 16); }
}
