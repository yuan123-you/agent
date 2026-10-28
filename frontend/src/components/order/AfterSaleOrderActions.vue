<template>
  <div class="order-after-sale" @click.stop>
    <button v-if="canApplyAfterSale(order,itemId)" type="button" class="after-sale-apply" @click="show=true">{{ order.status === 'PAID' ? '申请退款' : '申请售后' }}</button>
    <button v-if="cases.length" type="button" class="after-sale-progress" @click="router.push('/after-sales/' + cases[0].id)">{{ afterSaleStatusText(cases[0].status,cases[0].refundMode) }} <span aria-hidden="true">›</span></button>
    <AfterSaleApplyDialog v-if="show" v-model="show" :order-id="order.orderId" :order-item-id="itemId" @created="value=>{ emit('changed'); router.push('/after-sales/'+value.id) }" />
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { OrderVO } from '@/types/api'
import { afterSaleStatusText, canApplyAfterSale } from '@/utils/afterSale'
import AfterSaleApplyDialog from './AfterSaleApplyDialog.vue'
const props=defineProps<{order:OrderVO;itemId?:number}>()
const emit=defineEmits<{changed:[]}>()
const router=useRouter(),show=ref(false)
const cases=computed(()=>props.order.afterSales?.filter(value=>props.itemId===undefined||value.orderItemId===props.itemId) || [])
</script>
<style scoped>
.order-after-sale{display:inline-flex;flex-direction:column;align-items:flex-start;gap:5px;min-width:0}.order-after-sale:empty{display:none}.order-after-sale button{border:0;background:transparent;color:var(--el-text-color-regular);padding:5px 0;font:inherit;font-size:11px;cursor:pointer;white-space:nowrap}.order-after-sale .after-sale-progress{color:var(--mall-price);font-size:11px}.order-after-sale button:focus-visible{outline:2px solid var(--el-color-primary);outline-offset:2px}
</style>
