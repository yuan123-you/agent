<template>
  <el-dialog :model-value="modelValue" title="申请退款 / 售后" class="after-sale-apply-dialog" align-center width="min(560px, 94vw)" :close-on-click-modal="!submitting" :show-close="!submitting" @update:model-value="value => !submitting && emit('update:modelValue', value)">
    <LoadingState v-if="loading" variant="list" :count="2" />
    <div v-else-if="loadFailed" class="as-form-error" role="alert">申请信息加载失败 <button type="button" @click="load">重新加载</button></div>
    <form v-else class="as-apply-form" @submit.prevent="submit">
      <p class="as-form-note">退款金额以订单实付款、申请数量及审核结果为准。当前为模拟交易，不产生真实资金划转。</p>
      <label>售后商品<select v-model.number="itemId" :disabled="submitting"><option v-for="item in eligible" :key="item.orderItemId" :value="item.orderItemId">{{ item.productName }}{{ item.serviceTypes.length ? '' : '（' + item.unavailableReason + '）' }}</option></select></label>
      <p v-if="!selected?.serviceTypes.length" class="as-form-error">{{ selected?.unavailableReason || '没有可申请售后的商品' }}</p>
      <template v-else>
        <label>服务类型<select v-model="serviceType" :disabled="submitting"><option v-for="type in selected.serviceTypes" :key="type" :value="type">{{ afterSaleTypeText(type) }}</option></select></label>
        <p v-if="serviceType === 'EXCHANGE'" class="as-form-note">换货按原商品、原规格处理，不涉及补差价或跨商品换货。</p>
        <label>申请数量<input v-model.number="quantity" type="number" min="1" :max="selected.availableQuantity" step="1" required :disabled="submitting" /><small>最多 {{ selected.availableQuantity }} 件</small></label>
        <label>申请原因<select v-model="reason" :disabled="submitting"><option value="" disabled>请选择原因</option><option v-for="reasonOption in reasons" :key="reasonOption">{{ reasonOption }}</option></select></label>
        <label>问题说明<textarea v-model="description" rows="3" maxlength="450" placeholder="请描述商品问题或具体诉求，便于审核" :disabled="submitting" /></label>
        <label v-if="serviceType !== 'EXCHANGE'">退款金额（元）<input v-model.number="refundAmount" type="number" min="0" :max="quote ?? 0" step="0.01" required :disabled="submitting || quoteLoading" /><small>{{ quoteLoading ? '正在核算可退金额…' : quote === null ? '金额核算失败，请重试或调整数量' : '本次数量最高可退 ¥' + afterSaleMoney(quote) + '（已计入优惠分摊）' }}</small></label>
        <div class="as-evidence-field"><span>上传凭证 <small>选填，最多5张PNG/JPEG，每张不超过5MB</small></span><input aria-label="上传售后凭证" type="file" accept="image/png,image/jpeg" multiple :disabled="uploading || submitting || attachments.length >= 5" @change="uploadEvidence" /><div class="as-uploaded"><figure v-for="(file,index) in attachments" :key="file.token"><img :src="file.url" :alt="file.name" /><button type="button" :disabled="submitting" @click="removeEvidence(index)">移除</button></figure></div></div>
        <p v-if="formError" class="as-form-error" role="alert">{{ formError }}</p>
        <el-button type="primary" native-type="submit" :loading="submitting" :disabled="!reason || quote === null || quoteLoading || uploading || submitting">提交申请</el-button>
      </template>
    </form>
  </el-dialog>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import LoadingState from '@/components/common/LoadingState.vue'
import { apiAfterSaleApply, apiAfterSaleEligibility, apiAfterSaleQuote, apiAfterSaleUpload } from '@/api'
import type { AfterSaleEligibility, AfterSaleType, AfterSaleVO } from '@/types/aftersale'
import { afterSaleMoney, afterSaleTypeText } from '@/utils/afterSale'
const props=defineProps<{ modelValue: boolean; orderId: number; orderItemId?: number }>()
const emit=defineEmits<{ 'update:modelValue':[value:boolean]; created:[value:AfterSaleVO] }>()
const eligible=ref<AfterSaleEligibility[]>([]), loading=ref(false), loadFailed=ref(false), submitting=ref(false), uploading=ref(false), formError=ref('')
const itemId=ref<number>(), serviceType=ref<AfterSaleType>('REFUND_ONLY'), quantity=ref(1), reason=ref(''), description=ref(''), refundAmount=ref(0), quote=ref<number|null>(null), quoteLoading=ref(false)
const selected=computed(()=>eligible.value.find(item=>item.orderItemId===itemId.value))
const reasons=['不想要了 / 拍错了','商品质量问题','商品与描述不符','少件 / 漏发','物流异常','其他原因']
const attachments=ref<{token:string;url:string;name:string}[]>([])
const requestId=crypto.randomUUID()
let generation=0, quoteGeneration=0, disposed=false
async function load(){const current=++generation;loading.value=true;loadFailed.value=false;try{const result=await apiAfterSaleEligibility(props.orderId);if(current!==generation)return;eligible.value=result;itemId.value=props.orderItemId || result.find(item=>item.serviceTypes.length)?.orderItemId || result[0]?.orderItemId}catch{if(current===generation)loadFailed.value=true}finally{if(current===generation)loading.value=false}}
watch(selected, value=>{quantity.value=1;serviceType.value=value?.serviceTypes[0] || 'REFUND_ONLY'})
watch([itemId,quantity,serviceType],async()=>{const current=++quoteGeneration;quote.value=null;quoteLoading.value=false;formError.value='';if(!selected.value?.serviceTypes.includes(serviceType.value)||!Number.isInteger(quantity.value)||quantity.value<1||quantity.value>selected.value.availableQuantity)return;quoteLoading.value=true;try{const result=await apiAfterSaleQuote(props.orderId,itemId.value!,serviceType.value,quantity.value);if(current!==quoteGeneration)return;quote.value=Number(result.maxRefundAmount);refundAmount.value=quote.value}catch{if(current===quoteGeneration)formError.value='可退金额核算失败，请调整数量后重试'}finally{if(current===quoteGeneration)quoteLoading.value=false}})
watch(()=>props.modelValue, value=>{if(value)void load()},{immediate:true})
async function uploadEvidence(event:Event){const input=event.target as HTMLInputElement;const files=Array.from(input.files || []);input.value='';formError.value='';if(files.length+attachments.value.length>5){formError.value='最多上传5张凭证';return}uploading.value=true;try{for(const file of files){if(!['image/png','image/jpeg'].includes(file.type)||file.size>5*1024*1024)throw new Error('仅支持5MB以内PNG/JPEG图片');const result=await apiAfterSaleUpload(file);if(disposed)return;attachments.value.push({token:result.token,url:URL.createObjectURL(file),name:file.name})}}catch(error){formError.value=error instanceof Error?error.message:'凭证上传失败，请重试'}finally{uploading.value=false}}
function removeEvidence(index:number){const [file]=attachments.value.splice(index,1);if(file)URL.revokeObjectURL(file.url)}
async function submit(){formError.value='';if(submitting.value||uploading.value||quoteLoading.value||quote.value===null||!selected.value||!reason.value)return;if(!Number.isInteger(quantity.value)||quantity.value<1||quantity.value>selected.value.availableQuantity||!Number.isFinite(refundAmount.value)||refundAmount.value<0||refundAmount.value>quote.value){formError.value='请检查数量和退款金额';return}submitting.value=true;try{const result=await apiAfterSaleApply({orderId:props.orderId,orderItemId:itemId.value!,serviceType:serviceType.value,issueCategory:reason.value==='商品质量问题'?'QUALITY':reason.value==='商品与描述不符'||reason.value==='少件 / 漏发'?'MERCHANT':'PERSONAL',reason:[reason.value,description.value.trim()].filter(Boolean).join('：'),quantity:quantity.value,refundAmount:serviceType.value==='EXCHANGE'?0:refundAmount.value,evidence:attachments.value.map(file=>file.token),requestId});emit('created',result);emit('update:modelValue',false)}catch{formError.value='提交未完成，请检查提示后重试，已填写内容会保留'}finally{submitting.value=false}}
onBeforeUnmount(()=>{disposed=true;generation++;quoteGeneration++;attachments.value.forEach(file=>URL.revokeObjectURL(file.url))})
</script>
<style scoped>
:global(.after-sale-apply-dialog){align-self:center;}
:global(.after-sale-apply-dialog .el-dialog__body) {max-height:70dvh;overflow-y:auto;}
.as-apply-form :deep(.el-button--primary){background:var(--mall-price);border-color:var(--mall-price);color:var(--mall-surface);}

.as-apply-form{display:flex;flex-direction:column;gap:15px}.as-form-note{margin:0;padding:10px 12px;background:var(--mall-surface-2);font-size:12px;line-height:1.7;color:var(--el-text-color-secondary)}label,.as-evidence-field{display:flex;flex-direction:column;gap:7px;font-size:13px;color:var(--el-text-color-primary)}select,input:not([type=file]),textarea{width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid var(--mall-border);border-radius:6px;background:var(--mall-surface);color:inherit;font:inherit}small{font-size:11px;color:var(--el-text-color-secondary)}.as-form-error{font-size:12px;color:var(--mall-price)}.as-uploaded{display:flex;gap:10px;flex-wrap:wrap}figure{margin:0;display:flex;flex-direction:column;gap:4px}figure img{width:70px;height:70px;object-fit:cover;border-radius:6px}figure button{border:0;background:transparent;color:var(--el-text-color-secondary);cursor:pointer}input[type=file]{max-width:100%;font-size:11px}
</style>
