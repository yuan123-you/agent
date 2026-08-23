<template>
  <div
    class="page"
    v-infinite-scroll="loadMore"
    :infinite-scroll-disabled="loading || finished"
    :infinite-scroll-distance="60"
  >
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
          <el-image :src="row.imageUrl" fit="cover" style="width: 48px; height: 48px; border-radius: 4px">
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

    <!-- 上架模板弹窗：必填/选填分区 -->
    <el-dialog v-model="dialog" :title="editingId ? '编辑商品' : '按模板上架商品'" width="640px" top="4vh">
      <el-scrollbar max-height="60vh">
        <el-form :model="tpl" label-width="100px" :rules="rules" ref="formRef">
          <div class="section-title">基础信息（必填）</div>
          <el-form-item label="商品名" prop="name">
            <el-input v-model="tpl.name" placeholder="如：星耀 X6 Pro" />
          </el-form-item>
          <el-form-item label="品牌" prop="brand">
            <el-input v-model="tpl.brand" placeholder="品牌名" />
          </el-form-item>
          <el-form-item label="类目" prop="category">
            <el-select v-model="tpl.category" placeholder="选择类目">
              <el-option v-for="c in CATEGORIES" :key="c.code" :label="c.name" :value="c.code" />
            </el-select>
          </el-form-item>
          <el-form-item label="价格(元)" prop="price">
            <el-input-number v-model="tpl.price" :min="0.01" :precision="2" />
          </el-form-item>
          <el-form-item label="库存" prop="stock">
            <el-input-number v-model="tpl.stock" :min="0" />
          </el-form-item>
          <el-form-item label="商品简介" prop="sellingPoints">
            <el-input v-model="tpl.sellingPoints" placeholder="一句话卖点，如：5000万像素 大电池" />
          </el-form-item>
          <el-form-item label="商品图片" prop="imageUrl">
            <el-input v-model="tpl.imageUrl" placeholder="图片URL（如 https://picsum.photos/seed/x/600/600）">
              <template #append>
                <el-button @click="randomPic">随机生成</el-button>
              </template>
            </el-input>
            <el-image v-if="tpl.imageUrl" :src="tpl.imageUrl" fit="cover"
              style="width: 80px; height: 80px; border-radius: 6px; margin-top: 8px">
              <template #error><div class="mini-fb">?</div></template>
            </el-image>
          </el-form-item>

          <div class="section-title optional">详细信息（选填）</div>
          <el-form-item label="材质">
            <el-input v-model="tpl.material" placeholder="如：纯棉 / S925银 / ABS工程塑料" />
          </el-form-item>
          <el-form-item label="产地">
            <el-input v-model="tpl.origin" placeholder="如：广东省东莞市" />
          </el-form-item>
          <el-form-item label="发货地">
            <el-input v-model="tpl.shipFrom" placeholder="如：广东省广州市" />
          </el-form-item>
          <el-form-item label="生产日期">
            <el-input v-model="tpl.productionDate" placeholder="如：2026-06-15" />
          </el-form-item>
          <el-form-item label="参数JSON">
            <el-input v-model="tpl.specs" type="textarea" :rows="2" placeholder='{"屏幕":"6.7英寸","电池":"5000mAh"}' />
          </el-form-item>
          <el-form-item label="详细介绍">
            <el-input v-model="tpl.description" type="textarea" :rows="4" placeholder="图文介绍（支持 Markdown）" />
          </el-form-item>
        </el-form>
      </el-scrollbar>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存并上架</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  apiMerchantCreate, apiMerchantDelete, apiMerchantProducts, apiMerchantStatus, apiMerchantUpdate,
} from '@/api'
import { CATEGORIES, categoryName } from '@/constants/categories'
import type { ProductVO } from '@/types/api'

const products = ref<ProductVO[]>([])
const loading = ref(false)
const finished = ref(false)
const status = ref('')
const page = ref(1)
const total = ref(0)
const dialog = ref(false)
const saving = ref(false)
const editingId = ref<number | undefined>()
const formRef = ref<FormInstance>()

const emptyTpl = () => ({
  name: '', brand: '', category: '', price: undefined as number | undefined,
  stock: undefined as number | undefined, sellingPoints: '', imageUrl: '',
  material: '', origin: '', shipFrom: '', productionDate: '', specs: '', description: '',
})
const tpl = reactive(emptyTpl())

// 模板必填项校验（后端 Bean Validation 同步）
const rules: FormRules = {
  name: [{ required: true, message: '商品名为必填项', trigger: 'blur' }],
  brand: [{ required: true, message: '品牌为必填项', trigger: 'blur' }],
  category: [{ required: true, message: '类目为必填项', trigger: 'change' }],
  price: [{ required: true, message: '价格为必填项', trigger: 'blur' }],
  stock: [{ required: true, message: '库存为必填项', trigger: 'blur' }],
  sellingPoints: [{ required: true, message: '商品简介为必填项', trigger: 'blur' }],
  imageUrl: [{ required: true, message: '商品图片为必填项', trigger: 'blur' }],
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
    const result = await apiMerchantProducts({
      page: page.value, size: 20,
      ...(status.value ? { status: status.value } : {}),
    })
    products.value.push(...result.records)
    total.value = result.total
    if (result.records.length === 0 || products.value.length >= result.total) {
      finished.value = true
    } else {
      page.value++
    }
  } finally {
    loading.value = false
  }
}

function loadMore() {
  load()
}

function openCreate() {
  Object.assign(tpl, emptyTpl())
  editingId.value = undefined
  dialog.value = true
}

function openEdit(row: ProductVO) {
  Object.assign(tpl, {
    name: row.name, brand: row.brand, category: row.category, price: row.price,
    stock: row.stock, sellingPoints: row.sellingPoints || '', imageUrl: row.imageUrl || '',
    material: row.material || '', origin: row.origin || '', shipFrom: row.shipFrom || '',
    productionDate: row.productionDate || '', specs: row.specs || '', description: row.description || '',
  })
  editingId.value = row.id
  dialog.value = true
}

function randomPic() {
  tpl.imageUrl = `https://picsum.photos/seed/m${Date.now() % 100000}/600/600`
}

async function save() {
  await formRef.value?.validate()
  saving.value = true
  try {
    const body = { ...tpl }
    if (editingId.value) {
      await apiMerchantUpdate(editingId.value, body)
    } else {
      await apiMerchantCreate(body)
    }
    ElMessage.success(editingId.value ? '已保存' : '上架成功')
    dialog.value = false
    reload()
  } catch {
    // 拦截器已提示
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
.page {
  height: 100%;
  overflow-y: auto;
  box-sizing: border-box;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.page-title {
  margin: 0;
  flex: 1;
}

.section-title {
  font-weight: 700;
  font-size: 14px;
  color: var(--el-color-primary);
  margin: 6px 0 14px;
  padding-left: 8px;
  border-left: 3px solid var(--el-color-primary);
}

.section-title.optional {
  color: #909399;
  border-color: #c0c4cc;
  margin-top: 20px;
}

.mini-fb {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  color: #c0c4cc;
  font-size: 18px;
  font-weight: 700;
  border-radius: 4px;
}

.load-state {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 18px 0 24px;
}
</style>
