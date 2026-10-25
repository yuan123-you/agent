import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiCartAdd, apiCartList, apiCartRemove, apiCartUpdate, type CartRow } from '@/api'
import { useAuthStore } from './auth'
import { ElMessage } from 'element-plus'

export const useCartStore = defineStore('cart', () => {
  const auth = useAuthStore()
  const items = ref<CartRow[]>([])
  const loading = ref(false)
  const isDrawerOpen = ref(false)

  const cartCount = computed(() => {
    return items.value.reduce((sum, item) => sum + (item.quantity || 1), 0)
  })

  const totalAmount = computed(() => {
    return Number(
      items.value
        .filter((i) => i.checked === 1)
        .reduce((sum, i) => sum + Number(i.subtotal || i.price * i.quantity), 0)
        .toFixed(2)
    )
  })

  async function fetchCart() {
    if (!auth.isCustomer) return
    loading.value = true
    try {
      const data = await apiCartList()
      items.value = data.items || []
    } catch {
      // 游客或网络错误静默处理
    } finally {
      loading.value = false
    }
  }

  async function addToCart(productId: number, quantity = 1, skuId = 0, openDrawerOnSuccess = true) {
    if (!auth.isCustomer) {
      ElMessage.warning('请先登录后再加入购物车')
      return false
    }
    try {
      await apiCartAdd(productId, quantity, skuId)
      ElMessage.success('已成功加入购物车')
      await fetchCart()
      if (openDrawerOnSuccess) {
        isDrawerOpen.value = true
      }
      return true
    } catch (e: any) {
      ElMessage.error(e?.message || '加入购物车失败')
      return false
    }
  }

  async function updateQuantity(row: CartRow, quantity: number) {
    try {
      await apiCartUpdate(row.cartItemId, { quantity, checked: row.checked === 1 })
      row.quantity = quantity
      row.subtotal = Number((row.price * quantity).toFixed(2))
    } catch (e: any) {
      ElMessage.error(e?.message || '更新数量失败')
    }
  }

  async function removeItem(cartItemId: number) {
    try {
      await apiCartRemove(cartItemId)
      items.value = items.value.filter((i) => i.cartItemId !== cartItemId)
      ElMessage.success('商品已从购物车移除')
    } catch (e: any) {
      ElMessage.error(e?.message || '删除失败')
    }
  }

  function openDrawer() {
    const token = localStorage.getItem('token')
    if (!token) {
      ElMessage.warning('请先登录后查看购物车')
      return
    }
    isDrawerOpen.value = true
    void fetchCart()
  }

  function closeDrawer() {
    isDrawerOpen.value = false
  }

  return {
    items,
    loading,
    isDrawerOpen,
    cartCount,
    totalAmount,
    fetchCart,
    addToCart,
    updateQuantity,
    removeItem,
    openDrawer,
    closeDrawer,
  }
})
