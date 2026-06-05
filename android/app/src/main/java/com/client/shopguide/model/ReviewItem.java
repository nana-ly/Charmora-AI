package com.client.shopguide.model;

/**
 * 用户评论条目
 */
public class ReviewItem {
    private String nickname;
    private int rating;
    private String content;

    public ReviewItem() {}

    public ReviewItem(String nickname, int rating, String content) {
        this.nickname = nickname;
        this.rating = rating;
        this.content = content;
    }

    public String getNickname() { return nickname; }
    public void setNickname(String nickname) { this.nickname = nickname; }
    public int getRating() { return rating; }
    public void setRating(int rating) { this.rating = rating; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
}
