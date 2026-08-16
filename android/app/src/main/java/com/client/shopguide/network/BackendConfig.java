package com.client.shopguide.network;

import android.content.Context;
import android.content.SharedPreferences;

/** User-editable backend endpoint shared by every Android screen. */
public final class BackendConfig {
    private static final String PREFS = "charmora_settings";
    private static final String KEY_BASE_URL = "backend_base_url";
    public static final String DEFAULT_BASE_URL = "http://10.0.2.2:8000/";

    private BackendConfig() {}

    public static String getBaseUrl(Context context) {
        return normalize(context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_BASE_URL, DEFAULT_BASE_URL));
    }

    public static void setBaseUrl(Context context, String value) {
        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        preferences.edit().putString(KEY_BASE_URL, normalize(value)).apply();
    }

    public static String normalize(String value) {
        String result = value == null ? "" : value.trim();
        if (result.isEmpty()) result = DEFAULT_BASE_URL;
        if (!result.startsWith("http://") && !result.startsWith("https://")) {
            result = "http://" + result;
        }
        return result.endsWith("/") ? result : result + "/";
    }
}
