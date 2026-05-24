package com.client.shopguide;

import com.client.shopguide.model.ChatRequest;
import com.client.shopguide.model.ChatResponse;
import com.client.shopguide.model.RecommendRequest;
import com.client.shopguide.model.RecommendResponse;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.POST;

public interface ApiService {

    @POST("/recommend")
    Call<RecommendResponse> recommend(@Body RecommendRequest request);

    @POST("/chat")
    Call<ChatResponse> chat(@Body ChatRequest request);
}
