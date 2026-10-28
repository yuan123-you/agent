<template>
  <el-scrollbar class="as-scroll"><main class="as-page">
    <header class="as-page-header"><div><h1>{{ manage ? '售后管理' : '退款 / 售后' }}</h1><p>{{ manage ? '审核申请、处理退件与换货，所有操作保留记录' : '查看退款进度，跟进退货与换货' }}</p></div><button class="as-text-button" type="button" @click="router.push(manage ? (base.startsWith('/admin') ? '/admin/orders' : '/merchant/products') : '/orders')">{{ manage ? '返回管理' : '我的订单' }} ›</button></header>
    <div class="as-list-filter"><label>售后状态 <select v-model="status" @change="reload"><option value="">全部售后</option><option v-for="(label,key) in afterSaleStates" :key="key" :value="key">{{ label }}</option></select></label><span v-if="orderId">订单筛选中 <button class="as-text-button" @click="router.replace({query:{}})">清除</button></span><span v-if="!loading">共 {{ total }} 笔</span></div>
    <div class="as-list">
      <article v-for="item in records" :key="item.id" class="as-case-card">
        <header><span>{{ afterSaleTypeText(item.serviceType) }} <small>· {{ item.afterSaleNo }}</small></span><strong>{{ afterSaleStatusText(item.status,item.refundMode) }}</strong></header>
        <button class="as-product-button" type="button" @click="router.push(base+'/'+item.id)"><el-image :src="item.productImage" fit="cover" :alt="item.productName"><template #error><span class="as-image-fallback">商品</span></template></el-image><span><b>{{ item.productName }}</b><small>申请数量：{{ item.quantity }} 件</small><small>{{ afterSaleTime(item.createdAt) }}</small></span></button>
        <div class="as-case-footer"><span>{{ item.serviceType === 'EXCHANGE' || item.serviceType === 'ISSUE_REPORT' ? '不涉及退款' : '申请退款 ¥' + afterSaleMoney(item.requestedRefundAmount) }}</span><el-button size="small" round @click="router.push(base+'/'+item.id)">{{ manage && item.actions.length ? '处理售后' : '查看详情' }}</el-button></div>
      </article>
    </div>
    <LoadingState v-if="loading" variant="list" :count="3" />
    <div v-else-if="error" class="as-empty" role="alert"><h2>售后记录加载失败</h2><el-button @click="load">重新加载</el-button></div>
    <div v-else-if="!records.length" class="as-empty"><h2>暂无{{ status ? afterSaleStates[status] : '' }}售后记录</h2><p v-if="!manage">需要帮助时，可从订单中选择商品申请退款或售后</p><el-button v-if="!manage" @click="router.push('/orders')">查看我的订单</el-button></div>
    <div v-else class="as-load-more"><el-button v-if="!finished" text @click="load">加载更多</el-button><span v-else>已显示全部售后记录</span></div>
  </main></el-scrollbar>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import LoadingState from '@/components/common/LoadingState.vue'
import { apiAfterSales } from '@/api'
import type { AfterSaleVO } from '@/types/aftersale'
import { afterSaleBase,afterSaleMoney,afterSaleStates,afterSaleStatusText,afterSaleTime,afterSaleTypeText } from '@/utils/afterSale'
const route=useRoute(),router=useRouter(),base=computed(()=>afterSaleBase(route.path)),manage=computed(()=>!!route.meta.afterSaleManage)
const orderId=computed(()=>{const value=Number(route.query.orderId);return Number.isSafeInteger(value)&&value>0?value:undefined})
const records=ref<AfterSaleVO[]>([]),status=ref(''),page=ref(1),total=ref(0),loading=ref(false),error=ref(false),finished=ref(false)
let generation=0
function reload(){generation++;records.value=[];page.value=1;total.value=0;finished.value=false;loading.value=false;void load()}
async function load(){if(loading.value||finished.value)return;const current=generation;loading.value=true;error.value=false;try{const result=await apiAfterSales({page:page.value,size:20,...(status.value?{status:status.value}:{}),...(orderId.value?{orderId:orderId.value}:{})},manage.value);if(current!==generation)return;records.value.push(...result.records);total.value=result.total;finished.value=!result.records.length||records.value.length>=result.total;if(!finished.value)page.value++}catch{if(current===generation)error.value=true}finally{if(current===generation)loading.value=false}}
watch(()=>[route.path,orderId.value],reload,{immediate:true})
onBeforeUnmount(()=>generation++)
</script>
<style scoped src="./afterSale.css"></style>
