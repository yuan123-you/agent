package com.aimall.backend.chat;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class FaqServiceTest {

    private FaqService faqService;

    @BeforeEach
    void setUp() {
        faqService = new FaqService();
    }

    @Test
    @DisplayName("普通用户提问绝不被常见问题粗暴拦截，防止答非所问")
    void shouldNotInterceptNormalUserQueries() {
        assertNull(faqService.match("我想买个手机，请问有什么推荐吗？"));
        assertNull(faqService.match("可以帮我查下我的订单吗？"));
        assertNull(faqService.match("请问这款商品质量怎么样？"));
        assertNull(faqService.match("商品可以送货上门吗？"));
        assertNull(faqService.match("我想修改一下收货人姓名可以吗？"));
        assertNull(faqService.match("帮我推荐一款电脑"));
        assertNull(faqService.match("你好，在吗？"));
        assertNull(faqService.match("有什么优惠活动吗？"));
    }

    @Test
    @DisplayName("精准命中政策FAQ时返回固定答案")
    void shouldMatchExactOrHighSimilarityFaqs() {
        assertNotNull(faqService.match("退款多久能到账？"));
        assertNotNull(faqService.match("什么时候发货？"));
        assertNotNull(faqService.match("定制商品可以退货吗？"));
    }

    @Test
    @DisplayName("空消息或空白内容返回null")
    void shouldReturnNullForBlankOrNull() {
        assertNull(faqService.match(null));
        assertNull(faqService.match(""));
        assertNull(faqService.match("   "));
    }
}
