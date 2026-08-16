package com.client.shopguide.network;

import com.client.shopguide.model.RecommendResponse;
import com.google.gson.JsonObject;

import org.junit.Test;

import java.io.BufferedReader;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.Assert.assertEquals;

public class ChatSseClientTest {
    @Test
    public void consumesContractEventsAndIgnoresUnknownEvents() throws Exception {
        String stream =
                "event: start\ndata: {\"request_id\":\"r1\"}\n\n" +
                "event: thinking\ndata: {\"event\":\"enter\",\"node\":\"understand\",\"detail\":\"ok\"}\n\n" +
                "event: card\ndata: {\"item\":{\"product_id\":\"p1\"}}\n\n" +
                "event: delta\ndata: {\"text\":\"hello\"}\n\n" +
                "event: future_event\ndata: {\"ignored\":true}\n\n" +
                "event: items\ndata: {\"items\":[{\"product_id\":\"p1\",\"sku_id\":\"s1\",\"title\":\"Tea\"}],\"result_count\":4}\n\n" +
                "event: state\ndata: {\"state\":{\"action\":\"recommend\",\"result_count\":4}}\n\n" +
                "event: done\ndata: {}\n\n";
        RecordingListener listener = new RecordingListener();

        ChatSseClient.parseLines(new BufferedReader(new StringReader(stream)), () -> false, listener);

        assertEquals(
                java.util.Arrays.asList(
                        "thinking:enter:understand:ok",
                        "card:p1",
                        "delta:hello",
                        "items:1:4",
                        "state:recommend",
                        "done"
                ),
                listener.events
        );
    }

    @Test
    public void cancellationStopsAllLaterCallbacks() throws Exception {
        String stream =
                "event: delta\ndata: {\"text\":\"first\"}\n\n" +
                "event: delta\ndata: {\"text\":\"second\"}\n\n" +
                "event: done\ndata: {}\n\n";
        AtomicBoolean canceled = new AtomicBoolean(false);
        RecordingListener listener = new RecordingListener() {
            @Override public void onTextDelta(String content) {
                super.onTextDelta(content);
                canceled.set(true);
            }
        };

        ChatSseClient.parseLines(
                new BufferedReader(new StringReader(stream)), canceled::get, listener
        );

        assertEquals(java.util.Collections.singletonList("delta:first"), listener.events);
    }

    private static class RecordingListener implements ChatSseClient.StreamListener {
        final List<String> events = new ArrayList<>();

        @Override public void onTextDelta(String content) { events.add("delta:" + content); }
        @Override public void onItems(List<RecommendResponse.Item> items, int resultCount) {
            events.add("items:" + items.size() + ":" + resultCount);
        }
        @Override public void onState(String stateJson) {
            events.add("state:" + new com.google.gson.JsonParser().parse(stateJson)
                    .getAsJsonObject().get("action").getAsString());
        }
        @Override public void onDone() { events.add("done"); }
        @Override public void onError(String message) { events.add("error:" + message); }
        @Override public void onThinking(String event, String node, String detail) {
            events.add("thinking:" + event + ":" + node + ":" + detail);
        }
        @Override public void onCard(JsonObject itemData) {
            events.add("card:" + itemData.get("product_id").getAsString());
        }
        @Override public void onFallbackToRest() { events.add("fallback"); }
    }
}
