<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="direction => direction === 'bottom' && loadMore()">
    <div class="page">
    <div class="toolbar">
      <h3 class="page-title">商品管理（{{ total }}）</h3>
      <el-input v-model="keyword" placeholder="搜索商品/品牌" clearable style="width: 220px"
        @keyup.enter="reload" @clear="reload" />
      <el-select v-model="status" style="width: 120px" @change="reload">
        <el-option label="全部状态" value="" />
        <el-option label="在售" value="ON_SALE" />
        <el-option label="已下架" value="OFF_SHELF" />
      </el-select>
      <el-button type="primary" @click="openCreate">新建商品</el-button>
    </div>

    <el-table v-loading="loading && products.length === 0" :data="products" border stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="商品名" min-width="160" show-overflow-tooltip />
      <el-table-column prop="brand" label="品牌" width="90" />
      <el-table-column prop="category" label="类目" width="100">
        <template #default="{ row }">{{ categoryName(row.category) }}</template>
      </el-table-column>
      <el-table-column label="价格" width="100">
        <template #default="{ row }">￥{{ row.price }}</template>
      </el-table-column>
      <el-table-column prop="stock" label="库存" width="80" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'ON_SALE' ? 'success' : 'info'" size="small">
            {{ row.status === 'ON_SALE' ? '在售' : '已下架' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button size="small" :type="row.status === 'ON_SALE' ? 'warning' : 'success'"
            @click="toggle(row)">
            {{ row.status === 'ON_SALE' ? '下架' : '上架' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="loading" class="load-state">加载中...</div>
    <div v-else-if="finished && products.length > 0" class="load-state">— 没有更多了 —</div>

    <el-dialog v-model="dialog" title="新建商品" width="560px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="商品名">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="品牌">
          <el-input v-model="form.brand" />
        </el-form-item>
        <el-form-item label="类目">
          <el-select v-model="form.category">
            <el-option v-for="c in CATEGORIES" :key="c.code" :label="c.name" :value="c.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="价格(元)">
          <el-input-number v-model="form.price" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="库存">
          <el-input-number v-model="form.stock" :min="0" />
        </el-form-item>
        <el-form-item label="主图URL">
          <el-input v-model="form.imageUrl" placeholder="/images/x.jpg（可留空）" />
        </el-form-item>
        <el-form-item label="卖点">
          <el-input v-model="form.sellingPoints" placeholder="空格分隔，如：5000万像素 大电池" />
        </el-form-item>
        <el-form-item label="介绍">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  apiAdminProductCreate, apiAdminProductStatus, apiAdminProducts,
} from '@/api'
import { CATEGORIES, categoryName } from '@/constants/categories'
import type { ProductVO } from '@/types/api'

const products = ref<ProductVO[]>([])
const loading = ref(false)
const finished = ref(false)
const keyword = ref('')
const status = ref('')
const page = ref(1)
const total = ref(0)
const dialog = ref(false)
const saving = ref(false)

const emptyForm = (): Partial<ProductVO> => ({
  name: '', brand: '', category: 'PHONE', price: 0, stock: 0,
  imageUrl: '', sellingPoints: '', description: '',
})
const form = reactive<Partial<ProductVO>>(emptyForm())

function reload() {
  page.value = 1
  finished.value = false
  products.value = []
  load()
}

/** 懒加载：滚动到底部自动追加下一页 */
async function load() {
  if (loading.value || finished.value) return
  loading.value = true
  try {
    const result = await apiAdminProducts({
      page: page.value, size: 20,
      ...(keyword.value.trim() ? { keyword: keyword.value.trim() } : {}),
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
  Object.assign(form, emptyForm())
  dialog.value = true
}

async function save() {
  if (!form.name || !form.brand) {
    ElMessage.warning('请填写商品名与品牌')
    return
  }
  saving.value = true
  try {
    await apiAdminProductCreate(form)
    ElMessage.success('保存成功')
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
  await apiAdminProductStatus(row.id, target)
  ElMessage.success(target === 'ON_SALE' ? '已上架' : '已下架')
  reload()
}

onMounted(load)
</script>

<style scoped>
.page-scroll { height: 100%; }
.page {
  min-height: 100%;
  box-sizing: border-box;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.page-title {
  margin: 0;
  flex: 1;
  min-width: 140px;
}

.load-state {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 18px 0 24px;
}
</style>
