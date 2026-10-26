package com.aimall.backend.product;

import com.aimall.backend.common.BizException;
import com.aimall.backend.entity.BrowseHistory;
import com.aimall.backend.entity.Favorite;
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.*;
import java.util.List;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class FavoriteHistoryContractTest {
    @Test
    void favoriteAndHistoryRecordsExposeTheIdConsumedByProductCards() {
        FavoriteMapper favorites = mock(FavoriteMapper.class);
        BrowseHistoryMapper history = mock(BrowseHistoryMapper.class);
        ProductMapper products = mock(ProductMapper.class);
        Favorite f = new Favorite(); f.setProductId(488L);
        BrowseHistory h = new BrowseHistory(); h.setProductId(488L);
        Product p = new Product(); p.setId(488L); p.setName("商品");
        when(favorites.selectList(any())).thenReturn(List.of(f));
        when(history.selectList(any())).thenReturn(List.of(h));
        when(products.selectById(488L)).thenReturn(p);
        var controller = new FavoriteHistoryController(favorites, history, products, mock(UserMapper.class));
        for (var response : List.of(controller.list(7L, 1, 20), controller.history(7L, 1, 20))) {
            var records = (List<?>) response.getData().get("records");
            var row = (java.util.Map<?, ?>) records.get(0);
            assertEquals(488L, row.get("id")); assertEquals(488L, row.get("productId"));
        }
    }
    @Test
    void explicitLimitQueriesRejectNegativeOversizedAndOverflowingPagination() {
        var favorites = mock(FavoriteMapper.class); var history = mock(BrowseHistoryMapper.class);
        var controller = new FavoriteHistoryController(favorites, history, mock(ProductMapper.class), mock(UserMapper.class));
        for (long[] input : new long[][]{{0,20},{1,-1},{1,0},{1,501},{Long.MAX_VALUE,20}}) {
            assertThrows(BizException.class, () -> controller.list(7L, input[0], input[1]));
            assertThrows(BizException.class, () -> controller.history(7L, input[0], input[1]));
        }
        verifyNoInteractions(favorites, history);
    }
}
