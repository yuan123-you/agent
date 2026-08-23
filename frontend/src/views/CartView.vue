<template>
  <div class="page cart-page">
    <div class="cart-body">
      <!-- 商品列表 -->
      <div class="list">
        <div v-for="row in items" :key="row.cartItemId" class="cart-item">
          <el-checkbox :model-value="row.checked === 1" @change="toggleCheck(row)" />
          <el-image :src="row.imageUrl" fit="cover" class="pic" @click="goDetail(row.productId)">
            <template #error>
              <div class="pic-fb">{{ row.name.slice(0, 1) }}</div>
            </template>
          </el-image>
          <div class="info">
            <div class="name" @click="goDetail(row.productId)">{{ row.name }}</div>
            <div class="price">￥{{ row.price }}</div>
          </div>
          <div class="ops">
            <el-input-number :model-value="row.quantity" :min="1" :max="row.stock" size="small"
              @change="(v: number) => changeQty(row, v)" />
            <div class="subtotal">￥{{ row.subtotal }}</div>
            <el-button text type="danger" size="small" @click="remove(row)">删除</el-button>
          </div>
        </div>
        <el-empty v-if="!loading && items.length === 0" description="购物车空空如也，去逛逛吧">
          <el-button type="primary" @click="$router.push('/')">去逛逛</el-button>
        </el-empty>
      </div>
    </div>

    <!-- 结算栏（吸底） -->
    <div v-if="items.length > 0" class="checkout-bar">
      <el-checkbox :model-value="allChecked" @change="checkAll">全选</el-checkbox>
      <span class="total">合计：<b>￥{{ totalAmount }}</b></span>
      <el-button type="danger" :disabled="checkedCount === 0" @click="openCheckout">
        结算（{{ checkedCount }}）
      </el-button>
    </div>

    <!-- 收货信息弹窗 -->
    <el-dialog v-model="showCheckout" title="确认订单（模拟支付）" width="440px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="商品">
          <span>共 {{ checkedCount }} 件，合计 <b class="amount">￥{{ totalAmount }}</b></span>
        </el-form-item>
        <el-form-item v-if="addresses.length > 0" label="地址簿">
          <el-select v-model="selectedAddressId" placeholder="选择收货地址" style="width: 100%" @change="applyAddress">
            <el-option v-for="a in addresses" :key="a.addressId" :label="`${a.receiverName} ${a.receiverPhone} ${a.receiverAddress}`" :value="a.addressId" />
          </el-select>
        </el-form-item>
        <el-form-item label="收货人">
          <el-input v-model="form.receiverName" placeholder="收货人姓名" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.receiverPhone" placeholder="手机号" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.receiverAddress" type="textarea" :rows="2" placeholder="收货地址" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCheckout = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">提交订单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  apiAddresses, apiCartCheckAll, apiCartCheckout, apiCartList, apiCartRemove, apiCartUpdate, type CartRow,
} from '@/api'
import type { AddressVO } from '@/types/api'

const router = useRouter()
const items = ref<CartRow[]>([])
const loading = ref(false)
const totalAmount = ref(0)
const checkedCount = ref(0)
const showCheckout = ref(false)
const submitting = ref(false)
const form = reactive({ receiverName: '', receiverPhone: '', receiverAddress: '' })
const addresses = ref<AddressVO[]>([])
const selectedAddressId = ref<number | undefined>()

const allChecked = computed(() => items.value.length > 0 && checkedCount.value === items.value.length)

async function load() {
  loading.value = true
  try {
    const data = await apiCartList()
    items.value = data.items
    totalAmount.value = data.totalAmount
    checkedCount.value = data.checkedCount
  } finally {
    loading.value = false
  }
}

async function toggleCheck(row: CartRow) {
  await apiCartUpdate(row.cartItemId, { checked: row.checked !== 1 })
  load()
}

async function checkAll(checked: unknown) {
  await apiCartCheckAll(Boolean(checked))
  load()
}

async function changeQty(row: CartRow, qty: number) {
  await apiCartUpdate(row.cartItemId, { quantity: qty })
  load()
}

async function remove(row: CartRow) {
  await apiCartRemove(row.cartItemId)
  ElMessage.success('已删除')
  load()
}

/** 打开结算：加载地址簿，默认选中默认地址并预填表单 */
async function openCheckout() {
  showCheckout.value = true
  try {
    addresses.value = await apiAddresses()
    const dflt = addresses.value.find((a) => a.isDefault) || addresses.value[0]
    if (dflt) applyAddress(dflt.addressId)
  } catch {
    // 无地址簿时沿用手工填写
  }
}

function applyAddress(id: number) {
  const a = addresses.value.find((x) => x.addressId === id)
  if (!a) return
  selectedAddressId.value = a.addressId
  form.receiverName = a.receiverName
  form.receiverPhone = a.receiverPhone
  form.receiverAddress = a.receiverAddress
}

async function submit() {
  if (!form.receiverName || !form.receiverPhone || !form.receiverAddress) {
    ElMessage.warning('请完整填写收货信息')
    return
  }
  submitting.value = true
  try {
    const order = await apiCartCheckout({ ...form })
    ElMessage.success(`下单成功：${order.orderNo}`)
    showCheckout.value = false
    router.push(`/orders/${order.orderId}`)
  } catch {
    // 拦截器已提示
  } finally {
    submitting.value = false
  }
}

function goDetail(id: number) {
  router.push(`/products/${id}`)
}

onMounted(load)
</script>

<style scoped>
.cart-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.cart-body {
  flex: 1;
  overflow-y: auto;
  max-width: 960px;
  width: 100%;
  margin: 0 auto;
  padding: 16px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cart-item {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border-radius: 8px;
  padding: 12px;
}

.pic {
  width: 80px;
  height: 80px;
  border-radius: 6px;
  cursor: pointer;
  flex-shrink: 0;
}

.pic-fb {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  color: #c0c4cc;
  font-size: 28px;
  font-weight: 700;
}

.info {
  flex: 1;
  min-width: 0;
}

.name {
  font-weight: 600;
  cursor: pointer;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.price {
  color: var(--el-color-danger);
  margin-top: 6px;
}

.ops {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.subtotal {
  font-weight: 700;
  color: var(--el-color-danger);
  font-size: 15px;
}

.checkout-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-top: 1px solid #ebeef5;
  padding: 10px 20px;
  padding-bottom: calc(10px + env(safe-area-inset-bottom));
}

.checkout-bar .total {
  margin-left: auto;
  font-size: 15px;
}

.checkout-bar .total b {
  color: var(--el-color-danger);
  font-size: 20px;
}

.amount {
  color: var(--el-color-danger);
}

@media (max-width: 768px) {
  .cart-body {
    padding: 10px;
  }

  .cart-item {
    padding: 8px;
    gap: 8px;
  }

  .pic {
    width: 64px;
    height: 64px;
  }

  .ops {
    gap: 4px;
  }
}
</style>
