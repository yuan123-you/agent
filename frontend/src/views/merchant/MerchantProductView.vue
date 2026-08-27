<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="onEndReached">
    <div class="page">
      <div class="toolbar">
        <h3 class="page-title">商品管理（{{ total }}）</h3>
        <el-select v-model="status" style="width: 120px" @change="reload">
          <el-option label="全部状态" value="" />
          <el-option label="在售" value="ON_SALE" />
          <el-option label="已下架" value="OFF_SHELF" />
        </el-select>
        <el-button type="primary" @click="openCreate">+ 按模板上架</el-button>
      </div>

      <el-table v-loading="loading && products.length === 0" :data="products" border stripe>
        <el-table-column label="图片" width="80">
          <template #default="{ row }">
            <el-image :src="row.imageUrl" fit="cover" class="product-thumb">
              <template #error><div class="mini-fb">{{ (row.name || '?').slice(0, 1) }}</div></template>
            </el-image>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="商品名" min-width="180" show-overflow-tooltip />
        <el-table-column label="类目" width="100">
          <template #default="{ row }">{{ categoryName(row.category) }}</template>
        </el-table-column>
        <el-table-column label="价格" width="100">
          <template #default="{ row }">￥{{ row.price }}</template>
        </el-table-column>
        <el-table-column prop="stock" label="库存" width="80" />
        <el-table-column prop="sales" label="销量" width="80" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ON_SALE' ? 'success' : 'info'" size="small">
              {{ row.status === 'ON_SALE' ? '在售' : '已下架' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" :type="row.status === 'ON_SALE' ? 'warning' : 'success'" @click="toggle(row)">
              {{ row.status === 'ON_SALE' ? '下架' : '上架' }}
            </el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="loading" class="load-state">加载中...</div>
      <div v-else-if="finished && products.length > 0" class="load-state">— 没有更多了 —</div>
    </div>
  </el-scrollbar>

  <el-dialog v-model="dialog" :title="editingId ? '编辑商品' : '按模板上架商品'" width="680px" top="4vh">
    <el-scrollbar max-height="62vh">
      <el-form ref="formRef" :model="tpl" label-width="110px" :rules="rules">
        <div class="section-title">基础信息（必填）</div>
        <el-form-item label="商品名" prop="name"><el-input v-model="tpl.name" placeholder="如：星耀 X6 Pro" /></el-form-item>
        <el-form-item label="品牌" prop="brand"><el-input v-model="tpl.brand" placeholder="品牌名" /></el-form-item>
        <el-form-item label="类目" prop="category">
          <el-select v-model="tpl.category" placeholder="选择类目">
            <el-option v-for="c in CATEGORIES" :key="c.code" :label="c.name" :value="c.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="价格(元)" prop="price"><el-input-number v-model="tpl.price" :min="0.01" :precision="2" /></el-form-item>
        <el-form-item label="库存" prop="stock"><el-input-number v-model="tpl.stock" :min="0" /></el-form-item>
        <el-form-item label="商品简介" prop="sellingPoints">
          <el-input v-model="tpl.sellingPoints" placeholder="一句话介绍商品亮点" />
        </el-form-item>
        <el-form-item label="商品图片" prop="imageUrl">
          <el-upload
            class="image-uploader"
            accept="image/jpeg,image/png,image/webp"
            :show-file-list="false"
            :before-upload="beforeImageUpload"
            :http-request="uploadImage"
          >
            <el-image v-if="tpl.imageUrl" :src="tpl.imageUrl" fit="cover" class="image-preview">
              <template #error><div class="image-placeholder">重新选择图片</div></template>
            </el-image>
            <div v-else v-loading="uploading" class="image-placeholder">选择图片上传</div>
          </el-upload>
          <div class="field-tip">支持 JPG、PNG、WebP，图片不超过 5MB</div>
        </el-form-item>
        <el-form-item label="产地" prop="origin">
          <el-cascader v-model="originCodes" :options="regionData" placeholder="选择省、市、区" class="full-width" @change="onOriginChange" />
        </el-form-item>
        <el-form-item label="发货地" prop="shipFrom">
          <el-cascader v-model="shipFromCodes" :options="regionData" placeholder="选择省、市、区" class="full-width" @change="onShipFromChange" />
        </el-form-item>

        <div class="section-title optional">详细信息（选填）</div>
        <el-form-item label="材质"><el-input v-model="tpl.material" placeholder="如：纯棉 / S925银 / ABS工程塑料" /></el-form-item>
        <el-form-item label="生产日期"><el-input v-model="tpl.productionDate" placeholder="如：2026-06-15" /></el-form-item>
        <el-form-item label="商品信息">
          <div class="custom-info-list">
            <div v-for="(item, index) in customInfo" :key="index" class="custom-info-row">
              <el-input v-model="item.name" maxlength="30" placeholder="选项名称，如：屏幕" />
              <el-input v-model="item.content" maxlength="100" placeholder="选项内容，如：6.7英寸" />
              <el-button type="danger" plain @click="removeCustomInfo(index)">删除</el-button>
            </div>
            <el-button v-if="customInfo.length < MAX_CUSTOM_PRODUCT_INFO" plain @click="addCustomInfo">
              + 添加商品信息（最多5项）
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="详细介绍">
          <el-input v-model="tpl.description" type="textarea" :rows="4" placeholder="商品的详细介绍（支持 Markdown）" />
        </el-form-item>
      </el-form>
    </el-scrollbar>
    <template #footer>
      <el-button @click="dialog = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存并上架</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type UploadRawFile, type UploadRequestOptions } from 'element-plus'
import { regionData } from 'element-china-area-data'
import {
  apiMerchantCreate, apiMerchantDelete, apiMerchantProductImage, apiMerchantProducts, apiMerchantStatus, apiMerchantUpdate,
} from '@/api'
import type { RegionOption } from '@/components/address/addressForm'
import { CATEGORIES, categoryName } from '@/constants/categories'
import type { ProductVO } from '@/types/api'
import {
  MAX_CUSTOM_PRODUCT_INFO, isCompleteProductLocation, locationCodesForValue, locationValueForCodes, parseCustomProductInfo,
  serializeCustomProductInfo, validateCustomProductInfo, type CustomProductInfo,
} from './productForm'

const regions = regionData as RegionOption[]
const products = ref<ProductVO[]>([])
const loading = ref(false)
const finished = ref(false)
const status = ref('')
const page = ref(1)
const total = ref(0)
const dialog = ref(false)
const saving = ref(false)
const uploading = ref(false)
const editingId = ref<number>()
const formRef = ref<FormInstance>()
const originCodes = ref<string[]>([])
const shipFromCodes = ref<string[]>([])
const customInfo = ref<CustomProductInfo[]>([])

const emptyTpl = () => ({
  name: '', brand: '', category: '', price: undefined as number | undefined,
  stock: undefined as number | undefined, sellingPoints: '', imageUrl: '',
  material: '', origin: '', shipFrom: '', productionDate: '', description: '',
})
const tpl = reactive(emptyTpl())

const rules: FormRules = {
  name: [{ required: true, message: '商品名为必填项', trigger: 'blur' }],
  brand: [{ required: true, message: '品牌为必填项', trigger: 'blur' }],
  category: [{ required: true, message: '类目为必填项', trigger: 'change' }],
  price: [{ required: true, message: '价格为必填项', trigger: 'change' }],
  stock: [{ required: true, message: '库存为必填项', trigger: 'change' }],
  sellingPoints: [{ required: true, message: '商品简介为必填项', trigger: 'blur' }],
  imageUrl: [{ required: true, message: '请上传商品图片', trigger: 'change' }],
  origin: [{ validator: (_rule, _value, callback) => isCompleteProductLocation(originCodes.value) ? callback() : callback(new Error('请选择完整的省、市、区')), trigger: 'change' }],
  shipFrom: [{ validator: (_rule, _value, callback) => isCompleteProductLocation(shipFromCodes.value) ? callback() : callback(new Error('请选择完整的省、市、区')), trigger: 'change' }],
}

function reload() {
  page.value = 1
  finished.value = false
  products.value = []
  load()
}

async function load() {
  if (loading.value || finished.value) return
  loading.value = true
  try {
    const result = await apiMerchantProducts({ page: page.value, size: 20, ...(status.value ? { status: status.value } : {}) })
    products.value.push(...result.records)
    total.value = result.total
    if (result.records.length === 0 || products.value.length >= result.total) finished.value = true
    else page.value++
  } finally {
    loading.value = false
  }
}

function onEndReached(direction: string) {
  if (direction === 'bottom') load()
}

function openCreate() {
  Object.assign(tpl, emptyTpl())
  originCodes.value = []
  shipFromCodes.value = []
  customInfo.value = []
  editingId.value = undefined
  dialog.value = true
}

function openEdit(row: ProductVO) {
  Object.assign(tpl, {
    name: row.name, brand: row.brand, category: row.category, price: row.price,
    stock: row.stock, sellingPoints: row.sellingPoints || '', imageUrl: row.imageUrl || '',
    material: row.material || '', origin: row.origin || '', shipFrom: row.shipFrom || '',
    productionDate: row.productionDate || '', description: row.description || '',
  })
  originCodes.value = locationCodesForValue(regions, row.origin)
  shipFromCodes.value = locationCodesForValue(regions, row.shipFrom)
  customInfo.value = parseCustomProductInfo(row.specs)
  editingId.value = row.id
  dialog.value = true
}

function onOriginChange(codes: string[]) {
  tpl.origin = locationValueForCodes(regions, codes || [])
}

function onShipFromChange(codes: string[]) {
  tpl.shipFrom = locationValueForCodes(regions, codes || [])
}

function addCustomInfo() {
  if (customInfo.value.length < MAX_CUSTOM_PRODUCT_INFO) customInfo.value.push({ name: '', content: '' })
}

function removeCustomInfo(index: number) {
  customInfo.value.splice(index, 1)
}

function beforeImageUpload(file: UploadRawFile) {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    ElMessage.warning('仅支持 JPG、PNG、WebP 图片')
    return false
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过5MB')
    return false
  }
  return true
}

async function uploadImage(options: UploadRequestOptions) {
  uploading.value = true
  try {
    const result = await apiMerchantProductImage(options.file)
    tpl.imageUrl = result.url
    formRef.value?.clearValidate('imageUrl')
    options.onSuccess(result)
    ElMessage.success('图片上传成功')
  } catch (error) {
    options.onError(error instanceof Error ? error : new Error('图片上传失败'))
  } finally {
    uploading.value = false
  }
}

async function save() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  const infoError = validateCustomProductInfo(customInfo.value)
  if (infoError) return ElMessage.warning(infoError)

  saving.value = true
  try {
    const body = { ...tpl, specs: serializeCustomProductInfo(customInfo.value) }
    if (editingId.value) await apiMerchantUpdate(editingId.value, body)
    else await apiMerchantCreate(body)
    ElMessage.success(editingId.value ? '已保存' : '上架成功')
    dialog.value = false
    reload()
  } catch {
    // 请求拦截器已提示
  } finally {
    saving.value = false
  }
}

async function toggle(row: ProductVO) {
  const target = row.status === 'ON_SALE' ? 'OFF_SHELF' : 'ON_SALE'
  await apiMerchantStatus(row.id, target)
  ElMessage.success(target === 'ON_SALE' ? '已上架' : '已下架')
  reload()
}

async function remove(row: ProductVO) {
  await ElMessageBox.confirm('确定删除该商品？', '提示', { type: 'warning' })
  await apiMerchantDelete(row.id)
  ElMessage.success('已删除')
  reload()
}

onMounted(load)
</script>

<style scoped>
.page-scroll { height: 100%; }
.page { box-sizing: border-box; min-height: 100%; }
.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.page-title { margin: 0; flex: 1; }
.product-thumb, .mini-fb { width: 48px; height: 48px; border-radius: 4px; }
.section-title { font-weight: 700; font-size: 14px; color: var(--el-color-primary); margin: 6px 0 14px; padding-left: 8px; border-left: 3px solid var(--el-color-primary); }
.section-title.optional { color: #909399; border-color: #c0c4cc; margin-top: 20px; }
.mini-fb, .image-placeholder { display: flex; align-items: center; justify-content: center; background: #f5f7fa; color: #909399; }
.mini-fb { font-size: 18px; font-weight: 700; }
.image-uploader { line-height: 1; }
.image-preview, .image-placeholder { width: 112px; height: 112px; border: 1px dashed var(--el-border-color); border-radius: 6px; cursor: pointer; }
.field-tip { width: 100%; margin-top: 6px; color: #909399; font-size: 12px; }
.full-width, .custom-info-list { width: 100%; }
.custom-info-row { display: grid; grid-template-columns: 1fr 1.4fr auto; gap: 8px; margin-bottom: 8px; }
.load-state { text-align: center; color: #909399; font-size: 13px; padding: 18px 0 24px; }
</style>
