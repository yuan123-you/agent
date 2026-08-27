<template>
  <div class="checkout-address">
    <div v-loading="loading" class="addr-list">
      <div
        v-for="a in addresses"
        :key="a.addressId"
        class="addr-card"
        :class="{ selected: a.addressId === modelValue }"
        @click="select(a.addressId)"
      >
        <el-radio :model-value="modelValue" :value="a.addressId" class="addr-radio" />
        <div class="addr-info">
          <div class="addr-line1">
            <b>{{ a.receiverName }}</b>
            <span>{{ a.receiverPhone }}</span>
            <el-tag v-if="a.isDefault" size="small" type="success" round>默认</el-tag>
          </div>
          <div class="addr-loc">{{ a.receiverAddress }}</div>
          <div class="addr-ops">
            <el-button v-if="!a.isDefault" text type="primary" size="small" @click.stop="setDefault(a)">设为默认</el-button>
            <el-button text size="small" @click.stop="openEdit(a)">编辑</el-button>
            <el-button text type="danger" size="small" @click.stop="remove(a)">删除</el-button>
          </div>
        </div>
      </div>
      <div v-if="!loading && !addresses.length" class="addr-empty">暂无收货地址，请先新增</div>
    </div>
    <el-button type="primary" text :icon="Plus" @click="openAdd">新增收货地址</el-button>

    <!-- 新增 / 编辑地址弹窗 -->
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
          <el-checkbox v-model="form.isDefault">设为默认地址</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存地址</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { LocationInformation, Plus } from '@element-plus/icons-vue'
import { regionData } from 'element-china-area-data'
import {
  apiAddressAdd, apiAddressDefault, apiAddressDelete, apiAddresses, apiAddressUpdate, type AddressPayload,
} from '@/api'
import type { AddressVO } from '@/types/api'
import { codesForLabels, composeAddress, labelsForCodes, normalizeGeocode, type RegionOption } from './addressForm'

const props = defineProps<{ modelValue?: number }>()
const emit = defineEmits<{ (e: 'update:modelValue', value: number | undefined): void }>()

const addresses = ref<AddressVO[]>([])
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

function select(id: number) {
  emit('update:modelValue', id)
}

async function load() {
  loading.value = true
  try {
    const list = await apiAddresses()
    addresses.value = list
    // 若当前无选中且默认地址已删除/不存在，自动回填首个地址
    if (!props.modelValue && list.length) emit('update:modelValue', list[0].addressId)
  } finally {
    loading.value = false
  }
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
    ElMessage.success('地址已保存')
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

onMounted(load)
</script>

<style scoped>
.checkout-address { display: flex; flex-direction: column; gap: 8px; }
.addr-list { display: flex; flex-direction: column; gap: 8px; max-height: 300px; overflow-y: auto; }
.addr-card {
  display: flex; align-items: flex-start; gap: 8px; padding: 10px;
  border: 1px solid #ebeef5; border-radius: 8px; cursor: pointer;
  background: #fff; transition: border-color .15s, box-shadow .15s;
}
.addr-card.selected { border-color: var(--el-color-primary); box-shadow: 0 0 0 1px var(--el-color-primary); }
.addr-radio { margin-top: 2px; }
.addr-info { flex: 1; min-width: 0; }
.addr-line1 { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.addr-line1 span { color: #606266; font-size: 12px; }
.addr-loc { margin-top: 4px; color: #909399; font-size: 13px; line-height: 1.5; }
.addr-ops { margin-top: 4px; display: flex; gap: 4px; }
.addr-empty { color: #909399; font-size: 13px; padding: 10px 0; text-align: center; }
.two-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.region-row { display: flex; gap: 8px; width: 100%; }
.region-row .el-cascader { flex: 1; }
.located-label { margin-top: 7px; color: #8a6b46; font-size: 12px; }
</style>