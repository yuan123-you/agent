<template>
  <el-scrollbar class="as-scroll"><main class="as-page as-detail-page">
    <header class="as-page-header"><h1>售后详情</h1><button class="as-text-button" @click="router.push(base)">返回售后列表 ›</button></header>
    <LoadingState v-if="loading" variant="list" :count="3" />
    <div v-else-if="!record" class="as-empty" role="alert"><h2>售后信息暂不可用</h2><p>请检查权限或网络后重试</p><el-button @click="load">重新加载</el-button></div>
    <template v-else>
      <section class="as-status-panel"><span class="as-kicker">{{ afterSaleTypeText(record.serviceType) }} · {{ record.afterSaleNo }}</span><h2>{{ afterSaleStatusText(record.status,record.refundMode) }}</h2><p>{{ stateHint }}</p><p v-if="record.refundMode === 'SIMULATED'" class="as-simulation-note">演示交易：本流程不产生真实资金划转，不代表银行或支付渠道到账。</p></section>
      <div class="as-detail-grid">
        <div class="as-detail-main">
          <section class="as-panel"><h2>申请信息</h2><div class="as-product-line"><el-image :src="record.productImage" :alt="record.productName" fit="cover"><template #error><span class="as-image-fallback">商品</span></template></el-image><div><strong>{{ record.productName }}</strong><p>申请数量 {{ record.quantity }} 件</p><button class="as-text-button" @click="router.push(manage ? (base.startsWith('/admin') ? {path:'/admin/orders',query:{orderId:record.orderId}} : base) : '/orders/'+record.orderId)">订单 {{ record.orderNo }} ›</button></div></div><dl class="as-facts"><div><dt>服务类型</dt><dd>{{ afterSaleTypeText(record.serviceType) }}</dd></div><div><dt>申请原因</dt><dd>{{ record.reason }}</dd></div><div v-if="hasRefund"><dt>申请退款</dt><dd class="as-money">¥{{ afterSaleMoney(record.requestedRefundAmount) }}</dd></div><div v-if="hasRefund && record.approvedRefundAmount != null"><dt>核定退款</dt><dd>¥{{ afterSaleMoney(record.approvedRefundAmount) }}</dd></div><div><dt>申请时间</dt><dd>{{ afterSaleTime(record.createdAt) }}</dd></div><div><dt>当前处理方</dt><dd>{{ record.currentHandler === 'PLATFORM' ? '平台' : '商家' }}</dd></div><div v-if="record.decisionReason"><dt>审核说明</dt><dd>{{ record.decisionReason }}</dd></div><div v-if="record.refundReference"><dt>模拟退款编号</dt><dd>{{ record.refundReference }}</dd></div></dl><div v-if="record.evidence.length" class="as-proof-list"><el-image v-for="(token,index) in record.evidence" :key="token" :src="proofs[token]" :alt="'售后凭证 '+(index+1)" fit="cover" :preview-src-list="Object.values(proofs)"><template #error><span class="as-image-fallback">凭证加载失败</span></template></el-image></div></section>
          <section v-if="record.returnAddress" class="as-panel"><h2>退货信息</h2><p class="as-return-warning">请按审核提供的地址寄回商品，并保留寄件凭证。运费承担以协商及审核结果为准。</p><dl class="as-facts"><div><dt>收件人</dt><dd>{{ record.returnRecipient }} · {{ record.returnPhone }}</dd></div><div><dt>退货地址</dt><dd>{{ record.returnAddress }}</dd></div><div v-if="record.returnTrackingNo"><dt>退货物流</dt><dd>{{ record.returnCompany }} · {{ record.returnTrackingNo }}</dd></div></dl></section>
          <section v-if="record.exchangeTrackingNo" class="as-panel"><h2>换货物流</h2><p>{{ record.exchangeCompany }} · {{ record.exchangeTrackingNo }}</p><p class="as-muted">这里只展示登记的物流信息，不虚构运输轨迹或预计到达时间。</p></section>
        </div>
        <section class="as-panel as-history"><h2>处理进度</h2><ol><li v-if="!record.history.length"><strong>售后申请已创建</strong><p>历史申请暂无详细操作记录</p><time>{{ afterSaleTime(record.createdAt) }}</time></li><li v-for="(event,index) in [...record.history].reverse()" :key="index"><strong>{{ afterSaleActionText[event.action] || event.action }}</strong><p>{{ {BUYER:'买家',MERCHANT:'商家',PLATFORM:'平台'}[event.actorRole] || event.actorRole }} · {{ afterSaleStatusText(event.status,record.refundMode) }}</p><p v-if="event.message">{{ event.message }}</p><time>{{ afterSaleTime(event.at) }}</time></li></ol></section>
      </div>
      <footer class="as-action-bar"><button v-if="!manage" class="as-text-button" @click="router.push('/assistant')">联系客服</button><span v-else class="as-muted">操作结果将同步给买家</span><div><el-button v-for="action in record.actions" :key="action" :type="['APPROVE','REFUND','CONFIRM_EXCHANGE'].includes(action)?'primary':undefined" round @click="openAction(action)">{{ afterSaleActionText[action] || action }}</el-button></div></footer>
    </template>
    <el-dialog v-model="showAction" :title="afterSaleActionText[command.action]" width="min(500px,94vw)" :close-on-click-modal="!submitting" :show-close="!submitting">
      <form class="as-command-form" @submit.prevent="submitAction">
        <p>{{ actionHint }}</p>
        <template v-if="command.action === 'APPROVE' && record && ['RETURN_REFUND','EXCHANGE'].includes(record.serviceType)"><label>退货收件人<input v-model="command.recipient" maxlength="80" required :disabled="submitting" /></label><label>联系电话<input v-model="command.phone" maxlength="40" required :disabled="submitting" /></label><label>退货地址<textarea v-model="command.address" maxlength="500" rows="3" required :disabled="submitting" /></label></template>
        <template v-if="['RETURN','SHIP_EXCHANGE'].includes(command.action)"><label>物流公司<input v-model="command.company" maxlength="80" required :disabled="submitting" /></label><label>物流单号<input v-model="command.trackingNo" maxlength="100" required :disabled="submitting" /></label></template>
        <label v-if="['REJECT','APPEAL','TAKEOVER'].includes(command.action)">原因说明<textarea v-model="command.reason" maxlength="500" rows="3" required :disabled="submitting" /></label>
        <label v-if="command.action === 'RECEIVE'" class="as-checkbox"><input v-model="command.restock" type="checkbox" :disabled="submitting" />验收商品可再次销售，回补相应库存（损坏商品请勿勾选）</label>
        <p v-if="actionError" class="as-form-error" role="alert">{{ actionError }}</p><el-button native-type="submit" type="primary" :loading="submitting" :disabled="submitting">{{ submitting ? '正在提交' : '确认操作' }}</el-button>
      </form>
    </el-dialog>
  </main></el-scrollbar>
</template>
<script setup lang="ts">
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import LoadingState from '@/components/common/LoadingState.vue'
import { apiAfterSaleAction,apiAfterSaleDetail,apiAfterSaleEvidence } from '@/api'
import type { AfterSaleCommand,AfterSaleVO } from '@/types/aftersale'
import { afterSaleActionText,afterSaleBase,afterSaleMoney,afterSaleStatusText,afterSaleTime,afterSaleTypeText } from '@/utils/afterSale'
const route=useRoute(),router=useRouter(),base=computed(()=>afterSaleBase(route.path)),manage=computed(()=>!!route.meta.afterSaleManage)
const record=ref<AfterSaleVO|null>(null),loading=ref(false),proofs=ref<Record<string,string>>({}),showAction=ref(false),submitting=ref(false),actionError=ref(''),command=ref<AfterSaleCommand>({action:''})
let generation=0
const hasRefund=computed(()=>record.value && !['EXCHANGE','ISSUE_REPORT'].includes(record.value.serviceType))
const hints:Record<string,string>={PENDING_MERCHANT:'申请已提交，等待商家审核。',PENDING_PLATFORM:'申请已交由平台处理，请关注后续结果。',WAITING_RETURN:'申请已通过，请按下方地址寄回商品并填写退货物流。',RETURN_SHIPPED:'退货物流已登记，等待处理方验收。',WAITING_REFUND:'审核或退货验收已完成，等待执行模拟退款。',WAITING_EXCHANGE:'退件已验收，等待商家寄出换货商品。',EXCHANGE_SHIPPED:'换货商品已寄出，收到后请确认收货。',REFUNDED:'模拟退款已记录，请查看核定金额及模拟退款编号。',EXCHANGED:'换货流程已完成。',REJECTED:'请查看审核说明；若仍有异议，可按可用入口申请平台介入。',CANCELLED:'你已撤销本次申请，符合条件时可以重新申请。',RESOLVED:'本次问题反馈已处理。'}
const stateHint=computed(()=>hints[record.value?.status || ''] || '请查看处理进度和可用操作。')
const actionHint=computed(()=>({CONVERT_REFUND:'换货退件已验收，可转退款金额为 ¥'+afterSaleMoney(record.value?.convertRefundAmount)+'。确认后进入待退款，不会自动执行资金退款。',REFUND:'确认核定金额后执行模拟退款。此操作不产生真实资金划转；完成后不可重复执行。',APPROVE:'审核通过后，系统会进入待退款或待退货流程，不会直接标记退款完成。',RECEIVE:'请先核对退回商品。默认不回补库存，仅对验收确认可再次销售的商品勾选回补。',CANCEL:'确认撤销本次售后申请？撤销后将停止本次处理。',CONFIRM_EXCHANGE:'请确认已经收到并核对换货商品。',SHIP_EXCHANGE:'请填写真实换货物流，系统会检查并扣减换出商品库存。'} as Record<string,string>)[command.value.action] || '请核对信息后提交，操作会记录在处理进度中。')
function clearProofs(){Object.values(proofs.value).forEach(url=>URL.revokeObjectURL(url));proofs.value={}}
async function load(){const current=++generation;const id=Number(route.params.id);record.value=null;showAction.value=false;submitting.value=false;clearProofs();if(!Number.isSafeInteger(id)||id<=0)return;loading.value=true;try{const result=await apiAfterSaleDetail(id);if(current!==generation)return;record.value=result;await Promise.all(result.evidence.map(async token=>{try{const blob=await apiAfterSaleEvidence(id,token);if(current===generation)proofs.value[token]=URL.createObjectURL(blob)}catch{ /* API reports individual evidence failures. */ }}))}catch{ /* Keep an explicit retry state instead of claiming the case was deleted. */ }finally{if(current===generation)loading.value=false}}
function openAction(action:string){if(submitting.value)return;command.value={action,reason:'',recipient:'',phone:'',address:'',company:'',trackingNo:'',restock:false};actionError.value='';showAction.value=true}
async function submitAction(){if(submitting.value||!record.value||!record.value.actions.includes(command.value.action))return;const id=record.value.id,current=generation;submitting.value=true;actionError.value='';try{const result=await apiAfterSaleAction(id,{...command.value});if(current!==generation)return;record.value=result;showAction.value=false}catch{if(current===generation)actionError.value='操作未完成，请根据错误提示重试，填写内容会保留'}finally{if(current===generation)submitting.value=false}}
watch(()=>[route.params.id,route.path],()=>void load(),{immediate:true})
onBeforeUnmount(()=>{generation++;clearProofs()})
</script>
<style scoped src="./afterSale.css"></style>
