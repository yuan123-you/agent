<template>
  <section class="address-book" :class="{ compact }">
    <div class="book-head">
      <div>
        <div class="kicker">DELIVERY PROFILE</div>
        <h3>{{ title }}</h3>
        <p>保存默认地址，AI 下单时自动带入，无需重复填写。</p>
      </div>
      <el-button type="primary" @click="openAdd">新增地址</el-button>
    </div>

    <div v-loading="loading" class="address-list">
      <article v-for="address in list" :key="address.addressId" class="address-card">
        <div class="identity">
          <span class="avatar">{{ address.receiverName.slice(0, 1) }}</span>
          <div>
            <strong>{{ address.receiverName }}</strong>
            <span>{{ maskPhone(address.receiverPhone) }}</span>
          </div>
          <el-tag v-if="address.isDefault" type="success" size="small" round>默认地址</el-tag>
        </div>
        <p>{{ address.receiverAddress }}</p>
        <div class="card-actions">
          <el-button v-if="!address.isDefault" text type="primary" @click="setDefault(address)">设为默认</el-button>
          <el-button text @click="openEdit(address)">编辑</el-button>
          <el-button text type="danger" @click="remove(address)">删除</el-button>
        </div>
      </article>
      <el-empty v-if="!loading && !list.length" :image-size="70" description="还没有收货地址">
        <el-button type="primary" plain @click="openAdd">添加常用地址</el-button>
      </el-empty>
    </div>

    <el-dialog v-model="visible" :title="form.addressId ? '编辑收货地址' : '新增收货地址'" width="min(520px, 92vw)" destroy-on-close>
      <el-form label-position="top">
        <div class="two-columns">
          <el-form-item label="收货人">
            <el-input v-model="form.name" maxlength="30" placeholder="请输入姓名" />
          </el-form-item>
          <el-form-item label="手机号码">
            <el-input v-model="form.phone" maxlength="11" placeholder="用于配送联系" />
          </el-form-item>
        </div>
        <el-form-item label="省 / 市 / 区">
          <div class="region-row">
            <el-cascader
              v-model="form.regionCodes"
              :options="regionData"
              :props="{ expandTrigger: 'hover' }"
              placeholder="请选择省、市、区"
              clearable
              filterable
              @change="onRegionChange"
            />
            <el-button :loading="locating" @click="locate">
              <el-icon><LocationInformation /></el-icon>定位
            </el-button>
          </div>
          <div v-if="locatedLabel" class="located-label">已定位：{{ locatedLabel }}，请核对并补充门牌号</div>
        </el-form-item>
        <el-form-item label="详细地址">
          <el-input v-model="form.detailAddress" type="textarea" :rows="3" maxlength="120" show-word-limit
            placeholder="街道、门牌号、小区、楼栋及房间号" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="form.isDefault">设为默认地址（AI 下单自动使用）</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存地址</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { LocationInformation } from '@element-plus/icons-vue'
import { regionData } from 'element-china-area-data'
import {
  apiAddressAdd, apiAddressDefault, apiAddressDelete, apiAddresses, apiAddressUpdate, type AddressPayload,
} from '@/api'
import type { AddressVO } from '@/types/api'
import { codesForLabels, composeAddress, labelsForCodes, normalizeGeocode, type RegionOption } from './addressForm'

withDefaults(defineProps<{ compact?: boolean; title?: string }>(), { compact: false, title: '收货地址' })

const list = ref<AddressVO[]>([])
const loading = ref(false)
const visible = ref(false)
const submitting = ref(false)
const locating = ref(false)
const locatedLabel = ref('')
const form = reactive({
  addressId: undefined as number | undefined,
  name: '', phone: '', regionCodes: [] as string[], regionLabels: [] as string[],
  detailAddress: '', isDefault: false,
})

async function load() {
  loading.value = true
  try { list.value = await apiAddresses() } finally { loading.value = false }
}
function reset() {
  Object.assign(form, { addressId: undefined, name: '', phone: '', regionCodes: [], regionLabels: [], detailAddress: '', isDefault: false })
  locatedLabel.value = ''
}
function openAdd() { reset(); visible.value = true }
function openEdit(address: AddressVO) {
  const labels = [address.province, address.city, address.district].filter(Boolean) as string[]
  Object.assign(form, {
    addressId: address.addressId,
    name: address.receiverName,
    phone: address.receiverPhone,
    regionLabels: labels,
    regionCodes: codesForLabels(regionData as RegionOption[], labels),
    detailAddress: address.detailAddress || (labels.length ? '' : address.receiverAddress),
    isDefault: address.isDefault,
  })
  locatedLabel.value = ''
  visible.value = true
}
function onRegionChange(codes: string[]) {
  form.regionLabels = labelsForCodes(regionData as RegionOption[], codes || [])
  locatedLabel.value = ''
}
async function submit() {
  if (!form.name.trim() || !/^1\d{10}$/.test(form.phone.trim())) return ElMessage.warning('请填写正确的收货人和手机号')
  if (form.regionLabels.length < 3 || !form.detailAddress.trim()) return ElMessage.warning('请选择省市区并补充详细地址')
  submitting.value = true
  try {
    const [province, city, district] = form.regionLabels
    const payload: AddressPayload = {
      name: form.name.trim(), phone: form.phone.trim(), province, city, district,
      detailAddress: form.detailAddress.trim(), address: composeAddress(form.regionLabels, form.detailAddress),
      isDefault: form.isDefault,
    }
    if (form.addressId) await apiAddressUpdate(form.addressId, payload)
    else await apiAddressAdd(payload)
    visible.value = false
    ElMessage.success('地址已保存，下单时可自动使用')
    await load()
  } finally { submitting.value = false }
}
async function setDefault(address: AddressVO) {
  await apiAddressDefault(address.addressId)
  ElMessage.success('已设为默认地址')
  await load()
}
async function remove(address: AddressVO) {
  try {
    await ElMessageBox.confirm('删除后下单将无法使用该地址，确定继续？', '删除地址', { type: 'warning' })
    await apiAddressDelete(address.addressId)
    ElMessage.success('地址已删除')
    await load()
  } catch { /* user cancelled */ }
}
async function locate() {
  if (!navigator.geolocation) return ElMessage.warning('当前浏览器不支持定位，请手动选择地区')
  locating.value = true
  try {
    const position = await new Promise<GeolocationPosition>((resolve, reject) =>
      navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 }),
    )
    const { latitude, longitude } = position.coords
    const response = await fetch(`https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=zh`)
    if (!response.ok) throw new Error('reverse geocode failed')
    const region = normalizeGeocode(await response.json())
    const labels = [region.province, region.city, region.district].filter(Boolean)
    const codes = codesForLabels(regionData as RegionOption[], labels)
    if (region.detailAddress && !form.detailAddress.trim()) {
      form.detailAddress = region.detailAddress
    }
    if (codes.length) {
      form.regionCodes = codes
      form.regionLabels = labelsForCodes(regionData as RegionOption[], codes)
    }
    if (codes.length === 3) {
      locatedLabel.value = composeAddress(form.regionLabels, form.detailAddress)
      ElMessage.success(region.detailAddress ? '定位内容已填入，请核对并补充门牌号' : '定位成功，请补充详细门牌地址')
    } else {
      locatedLabel.value = composeAddress(labels, form.detailAddress)
      ElMessage.warning('已填入可识别的位置，请在菜单中确认省市区')
    }
  } catch {
    ElMessage.warning('定位失败，请检查定位权限或手动填写')
  } finally { locating.value = false }
}
function maskPhone(phone: string) { return phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2') }

onMounted(load)
</script>

<style scoped>
.address-book { background: #fff; border-radius: 16px; padding: 20px; }
.book-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.book-head h3 { margin: 3px 0 5px; font-size: 19px; }
.book-head p { margin: 0; color: #8a8178; font-size: 13px; }
.kicker { color: #b46b2b; font-size: 10px; font-weight: 800; letter-spacing: .15em; }
.address-list { display: grid; gap: 10px; margin-top: 16px; min-height: 80px; }
.address-card { padding: 14px; border: 1px solid #ece8e2; border-radius: 12px; background: #fffdfa; }
.identity { display: flex; align-items: center; gap: 9px; }
.identity > div { display: flex; align-items: baseline; gap: 8px; flex: 1; min-width: 0; }
.identity span:not(.avatar) { color: #8a8279; font-size: 12px; }
.avatar { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 50%; color: #fff; background: #b67a43; font-weight: 700; }
.address-card p { margin: 10px 0 5px 39px; color: #5f5851; font-size: 13px; line-height: 1.55; }
.card-actions { display: flex; justify-content: flex-end; }
.two-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.region-row { display: flex; gap: 8px; width: 100%; }
.region-row .el-cascader { flex: 1; }
.located-label { margin-top: 7px; color: #8a6b46; font-size: 12px; }
.compact { margin-top: 14px; }
@media (max-width: 520px) {
  .address-book { padding: 16px; }
  .book-head { align-items: center; }
  .book-head p { display: none; }
  .two-columns { grid-template-columns: 1fr; gap: 0; }
  .identity > div { align-items: flex-start; flex-direction: column; gap: 1px; }
  .address-card p { margin-left: 0; }
}
</style>
