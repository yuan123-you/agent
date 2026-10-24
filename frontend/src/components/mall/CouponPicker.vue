<template>
  <div class="coupon-picker" v-loading="loading">
    <el-radio-group :model-value="modelValue" class="coupon-list" @update:model-value="onPick">
      <el-radio v-for="c in coupons" :key="c.userCouponId" :value="c.userCouponId"
        :disabled="!c.usable" class="coupon-item">
        <div class="coupon-body">
          <div class="coupon-amount"><i>￥</i>{{ c.discountValue }}</div>
          <div class="coupon-info">
            <div class="coupon-name">{{ c.name }}</div>
            <div class="coupon-rule">
              {{ c.minAmount > 0 ? `满 ${c.minAmount} 可用` : '无门槛' }} · {{ shortExpire(c.expireAt) }}前有效
            </div>
          </div>
          <el-tag v-if="!c.usable" size="small" type="info" effect="plain">未达门槛</el-tag>
          <el-tag v-else size="small" type="danger" effect="plain">-{{ c.discount }}</el-tag>
        </div>
      </el-radio>
    </el-radio-group>
    <el-empty v-if="!loading && coupons.length === 0" description="暂无可用优惠券" :image-size="56" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { apiUsableCoupons } from '@/api'
import type { UsableCouponVO } from '@/types/api'

const props = defineProps<{ modelValue?: number; amount: number }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: number | undefined): void
  (e: 'discount', v: number): void
}>()

const coupons = ref<UsableCouponVO[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    coupons.value = (await apiUsableCoupons(props.amount)) || []
    // 金额变化导致选中券不再可用时清空选择
    const selected = coupons.value.find((c) => c.userCouponId === props.modelValue)
    if (props.modelValue && (!selected || !selected.usable)) {
      emit('update:modelValue', undefined)
      emit('discount', 0)
    } else if (selected) {
      emit('discount', selected.discount)
    }
  } finally {
    loading.value = false
  }
}

function onPick(v: unknown) {
  const id = typeof v === 'number' ? v : undefined
  emit('update:modelValue', id)
  const selected = coupons.value.find((c) => c.userCouponId === id)
  emit('discount', selected?.usable ? selected.discount : 0)
}

function shortExpire(iso: string): string {
  return (iso || '').slice(0, 10)
}

onMounted(load)
watch(() => props.amount, load)
</script>

<style scoped>
.coupon-picker {
  min-height: 72px;
}

.coupon-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.coupon-item {
  margin-right: 0;
  width: 100%;
}

.coupon-item :deep(.el-radio__label) {
  width: 100%;
}

.coupon-body {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.coupon-amount {
  flex: none;
  color: var(--el-color-danger);
  font-weight: 700;
  font-size: 20px;
  min-width: 64px;
}

.coupon-amount i {
  font-style: normal;
  font-size: 12px;
}

.coupon-info {
  flex: 1;
  min-width: 0;
}

.coupon-name {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.coupon-rule {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  margin-top: 2px;
}
</style>
