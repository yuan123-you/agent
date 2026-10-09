package com.aimall.backend.mapper;

import com.aimall.backend.entity.CartItem;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.*;

@Mapper
public interface CartItemMapper extends BaseMapper<CartItem> {
    @Update("UPDATE cart_item SET quantity = quantity + #{delta}, updated_at = CURRENT_TIMESTAMP "
            + "WHERE user_id = #{userId} AND product_id = #{productId} AND #{delta} > 0 "
            + "AND quantity <= (SELECT stock FROM product WHERE id = #{productId} "
            + "AND status = 'ON_SALE' AND deleted = 0) - #{delta}")
    int increment(@Param("userId") Long userId, @Param("productId") Long productId, @Param("delta") int delta);

    @Insert("INSERT INTO cart_item(user_id, product_id, quantity, checked, created_at, updated_at) "
            + "SELECT #{userId}, id, #{quantity}, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM product "
            + "WHERE id = #{productId} AND status = 'ON_SALE' AND deleted = 0 "
            + "AND #{quantity} > 0 AND stock >= #{quantity}")
    int insertGuarded(@Param("userId") Long userId, @Param("productId") Long productId, @Param("quantity") int quantity);

    @Update("<script>UPDATE cart_item SET quantity = #{quantity}, updated_at = CURRENT_TIMESTAMP "
            + "<if test='checked != null'>, checked = #{checked}</if> "
            + "WHERE id = #{id} AND user_id = #{userId} AND #{quantity} > 0 "
            + "AND #{quantity} &lt;= (SELECT stock FROM product WHERE id = cart_item.product_id "
            + "AND status = 'ON_SALE' AND deleted = 0)</script>")
    int setQuantity(@Param("id") Long id, @Param("userId") Long userId,
                    @Param("quantity") int quantity, @Param("checked") Integer checked);
}
