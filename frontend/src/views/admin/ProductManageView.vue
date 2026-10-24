<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="tab === 'products' && direction === 'bottom' && loadMore()">
    <div class="page">
    <el-tabs v-model="tab">
      <!-- ========== 商品 ========== -->
      <el-tab-pane label="商品" name="products">
        <div class="toolbar">
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
          <el-table-column label="规格" width="70">
            <template #default="{ row }">
              <el-tag size="small" :type="skuCountCache[row.id] ? 'primary' : 'info'" effect="plain">
                {{ skuCountCache[row.id] || 0 }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'ON_SALE' ? 'success' : 'info'" size="small">
                {{ row.status === 'ON_SALE' ? '在售' : '已下架' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openSkus(row)">规格</el-button>
              <el-button size="small" :type="row.status === 'ON_SALE' ? 'warning' : 'success'"
                @click="toggle(row)">
                {{ row.status === 'ON_SALE' ? '下架' : '上架' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="loading" class="load-state">加载中...</div>
        <div v-else-if="finished && products.length > 0" class="load-state">— 没有更多了 —</div>

        <el-dialog v-model="dialog" title="新建商品" width="min(560px, 92vw)">
          <el-form :model="form" label-width="90px">
            <el-form-item label="商品名">
              <el-input v-model="form.name" />
            </el-form-item>
            <el-form-item label="品牌">
              <el-select v-model="form.brandId" placeholder="选择品牌" filterable style="width: 100%">
                <el-option v-for="b in adminBrandList" :key="b.id" :label="b.name" :value="b.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="类目">
              <el-cascader v-model="categoryPath" :options="categoryTree" :props="cascaderProps"
                placeholder="选择分类" style="width: 100%" />
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

        <!-- SKU 规格管理弹窗 -->
        <el-dialog v-model="skuDialog" :title="`规格管理 - ${skuProduct?.name || ''}`" width="min(680px, 94vw)">
          <el-table :data="skuList" border size="small">
            <el-table-column label="规格" min-width="160">
              <template #default="{ row }">{{ spText(row.spData) }}</template>
            </el-table-column>
            <el-table-column label="价格" width="90">
              <template #default="{ row }">￥{{ row.price }}</template>
            </el-table-column>
            <el-table-column prop="stock" label="库存" width="70" />
            <el-table-column prop="sale" label="销量" width="70" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'ENABLE' ? 'success' : 'info'">
                  {{ row.status === 'ENABLE' ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-button size="small" @click="toggleSkuStatus(row)">
                  {{ row.status === 'ENABLE' ? '停用' : '启用' }}
                </el-button>
                <el-popconfirm title="删除该规格？" @confirm="removeSku(row)">
                  <template #reference>
                    <el-button size="small" type="danger">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>

          <el-divider content-position="left">新增规格</el-divider>
          <div class="sku-form">
            <el-input v-model="skuForm.spText" placeholder="属性名:属性值，多属性逗号分隔，如：颜色:黑色,容量:256G" style="flex: 1" />
            <el-input-number v-model="skuForm.price" :min="0" :precision="2" placeholder="价格" style="width: 130px" />
            <el-input-number v-model="skuForm.stock" :min="0" placeholder="库存" style="width: 120px" />
            <el-button type="primary" :loading="skuSaving" @click="createSku">添加</el-button>
          </div>
        </el-dialog>
      </el-tab-pane>

      <!-- ========== 分类 ========== -->
      <el-tab-pane label="分类" name="categories">
        <div class="toolbar">
          <span class="tab-hint">层级分类（对标 mall：最多两级），控制导航与列表筛选</span>
          <el-button type="primary" @click="openCategoryCreate()">新增一级分类</el-button>
        </div>
        <el-table :data="categoryTree" border row-key="id" default-expand-all>
          <el-table-column label="分类名称" min-width="160">
            <template #default="{ row }">{{ categoryName(row.name) }}</template>
          </el-table-column>
          <el-table-column label="在售商品" width="90">
            <template #default="{ row }">{{ row.productCount || 0 }}</template>
          </el-table-column>
          <el-table-column label="导航栏" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="row.navStatus === 1 ? 'success' : 'info'">
                {{ row.navStatus === 1 ? '显示' : '隐藏' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="row.showStatus === 1 ? 'success' : 'info'">
                {{ row.showStatus === 1 ? '显示' : '隐藏' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="sort" label="排序" width="70" />
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-button v-if="row.level === 1" size="small" @click="openCategoryCreate(row.id)">加子分类</el-button>
              <el-button size="small" @click="toggleCategoryNav(row)">
                {{ row.navStatus === 1 ? '隐藏导航' : '显示导航' }}
              </el-button>
              <el-popconfirm title="删除该分类？" @confirm="removeCategory(row)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="categoryDialog" :title="categoryForm.parentId ? '新增子分类' : '新增一级分类'" width="420px">
          <el-form :model="categoryForm" label-width="80px">
            <el-form-item label="名称">
              <el-input v-model="categoryForm.name" placeholder="分类名称" />
            </el-form-item>
            <el-form-item label="排序">
              <el-input-number v-model="categoryForm.sort" :min="0" />
            </el-form-item>
            <el-form-item label="导航栏">
              <el-switch v-model="categoryForm.navStatus" :active-value="1" :inactive-value="0" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="categoryDialog = false">取消</el-button>
            <el-button type="primary" :loading="categorySaving" @click="saveCategory">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- ========== 品牌 ========== -->
      <el-tab-pane label="品牌" name="brands">
        <div class="toolbar">
          <span class="tab-hint">品牌库（logo、品牌故事在商品页展示）</span>
          <el-button type="primary" @click="brandDialog = true">新增品牌</el-button>
        </div>
        <el-table :data="adminBrandList" border>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="name" label="品牌名称" min-width="140" />
          <el-table-column prop="firstLetter" label="首字母" width="80" />
          <el-table-column prop="productCount" label="商品数" width="80" />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="row.showStatus === 1 ? 'success' : 'info'">
                {{ row.showStatus === 1 ? '显示' : '隐藏' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button size="small" @click="toggleBrandStatus(row)">
                {{ row.showStatus === 1 ? '隐藏' : '显示' }}
              </el-button>
              <el-popconfirm title="删除该品牌？" @confirm="removeBrand(row)">
                <template #reference>
                  <el-button size="small" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="brandDialog" title="新增品牌" width="460px">
          <el-form :model="brandForm" label-width="80px">
            <el-form-item label="名称">
              <el-input v-model="brandForm.name" placeholder="品牌名称" />
            </el-form-item>
            <el-form-item label="首字母">
              <el-input v-model="brandForm.firstLetter" placeholder="如 A" maxlength="1" style="width: 100px" />
            </el-form-item>
            <el-form-item label="logo">
              <el-input v-model="brandForm.logo" placeholder="logo 图片 URL（可留空）" />
            </el-form-item>
            <el-form-item label="品牌故事">
              <el-input v-model="brandForm.brandStory" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="brandDialog = false">取消</el-button>
            <el-button type="primary" :loading="brandSaving" @click="saveBrand">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
      <!-- ========== 营销 ========== -->
      <el-tab-pane label="营销" name="promotions">
        <div class="toolbar">
          <span class="tab-hint">优惠券与限时秒杀（下单自动生效，取消订单自动回补）</span>
          <el-button type="primary" @click="couponDialog = true">新建优惠券</el-button>
          <el-button @click="seckillDialog = true">新建秒杀</el-button>
        </div>
        <el-tabs v-model="promoTab">
          <el-tab-pane label="优惠券" name="coupons">
            <el-table :data="couponList" border size="small">
              <el-table-column prop="id" label="ID" width="60" />
              <el-table-column prop="name" label="名称" min-width="140" />
              <el-table-column label="面额/门槛" width="130">
                <template #default="{ row }">￥{{ row.discountValue }} / 满{{ row.minAmount }}</template>
              </el-table-column>
              <el-table-column label="领取量" width="90">
                <template #default="{ row }">{{ row.receivedCount }}/{{ row.totalCount }}</template>
              </el-table-column>
              <el-table-column label="有效期" width="180">
                <template #default="{ row }">{{ fmtWindow(row.startTime, row.endTime) }}</template>
              </el-table-column>
              <el-table-column prop="validDays" label="用券天数" width="90" />
              <el-table-column label="状态" width="80">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.status === 'ENABLE' ? 'success' : 'info'">
                    {{ row.status === 'ENABLE' ? '进行中' : '已下架' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150">
                <template #default="{ row }">
                  <el-button size="small" @click="toggleCoupon(row)">
                    {{ row.status === 'ENABLE' ? '下架' : '上架' }}
                  </el-button>
                  <el-popconfirm title="删除该券？" @confirm="removeCoupon(row)">
                    <template #reference>
                      <el-button size="small" type="danger">删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="秒杀" name="seckills">
            <el-table :data="seckillList" border size="small">
              <el-table-column prop="id" label="ID" width="60" />
              <el-table-column prop="productId" label="商品ID" width="80" />
              <el-table-column label="秒杀价" width="90">
                <template #default="{ row }">￥{{ row.seckillPrice }}</template>
              </el-table-column>
              <el-table-column prop="seckillStock" label="秒杀库存" width="90" />
              <el-table-column prop="seckillLimit" label="限购" width="70" />
              <el-table-column label="活动时间" width="300">
                <template #default="{ row }">{{ fmtWindow(row.startTime, row.endTime) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="80">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.status === 'ENABLE' ? 'success' : 'info'">
                    {{ row.status === 'ENABLE' ? '启用' : '停用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150">
                <template #default="{ row }">
                  <el-button size="small" @click="toggleSeckill(row)">
                    {{ row.status === 'ENABLE' ? '停用' : '启用' }}
                  </el-button>
                  <el-popconfirm title="删除该活动？" @confirm="removeSeckill(row)">
                    <template #reference>
                      <el-button size="small" type="danger">删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>

        <!-- 新建优惠券 -->
        <el-dialog v-model="couponDialog" title="新建优惠券" width="460px">
          <el-form :model="couponForm" label-width="90px">
            <el-form-item label="券名称">
              <el-input v-model="couponForm.name" placeholder="如：全场满100减20" />
            </el-form-item>
            <el-form-item label="优惠金额">
              <el-input-number v-model="couponForm.discountValue" :min="0.01" :precision="2" />
            </el-form-item>
            <el-form-item label="使用门槛">
              <el-input-number v-model="couponForm.minAmount" :min="0" :precision="2" />
              <span class="form-hint">0 = 无门槛</span>
            </el-form-item>
            <el-form-item label="发行量">
              <el-input-number v-model="couponForm.totalCount" :min="1" />
            </el-form-item>
            <el-form-item label="领券时间">
              <el-date-picker v-model="couponWindow" type="datetimerange"
                value-format="YYYY-MM-DDTHH:mm:ss" start-placeholder="开始" end-placeholder="结束"
                style="width: 100%" />
            </el-form-item>
            <el-form-item label="用券天数">
              <el-input-number v-model="couponForm.validDays" :min="1" :max="365" />
              <span class="form-hint">领取后有效天数</span>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="couponDialog = false">取消</el-button>
            <el-button type="primary" :loading="promoSaving" @click="saveCoupon">保存</el-button>
          </template>
        </el-dialog>

        <!-- 新建秒杀 -->
        <el-dialog v-model="seckillDialog" title="新建秒杀活动" width="460px">
          <el-form :model="seckillForm" label-width="90px">
            <el-form-item label="商品ID">
              <el-input v-model="seckillForm.productId" placeholder="商品ID（商品页签可查）"
                @input="(v: string) => (seckillForm.productId = v.replace(/\D/g, ''))" />
            </el-form-item>
            <el-form-item label="秒杀价">
              <el-input-number v-model="seckillForm.seckillPrice" :min="0.01" :precision="2" />
            </el-form-item>
            <el-form-item label="秒杀库存">
              <el-input-number v-model="seckillForm.seckillStock" :min="1" />
            </el-form-item>
            <el-form-item label="每人限购">
              <el-input-number v-model="seckillForm.seckillLimit" :min="1" :max="10" />
            </el-form-item>
            <el-form-item label="活动时间">
              <el-date-picker v-model="seckillWindow" type="datetimerange"
                value-format="YYYY-MM-DDTHH:mm:ss" start-placeholder="开始" end-placeholder="结束"
                style="width: 100%" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="seckillDialog = false">取消</el-button>
            <el-button type="primary" :loading="promoSaving" @click="saveSeckill">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  apiAdminBrandCreate, apiAdminBrandDelete, apiAdminBrandUpdate, apiAdminBrands,
  apiAdminCatalogCategories, apiAdminCategoryCreate, apiAdminCategoryDelete, apiAdminCategoryUpdate,
  apiAdminCouponCreate, apiAdminCouponDelete, apiAdminCouponUpdate, apiAdminCoupons,
  apiAdminProductCreate, apiAdminProductStatus, apiAdminProducts,
  apiAdminSeckillCreate, apiAdminSeckillDelete, apiAdminSeckillUpdate, apiAdminSeckills,
  apiAdminSkuCreate, apiAdminSkuDelete, apiAdminSkuUpdate, apiAdminSkus,
} from '@/api'
import { categoryName } from '@/constants/categories'
import type { BrandVO, CategoryVO, ProductVO, SkuVO } from '@/types/api'

const tab = ref('products')

// ---------- 商品列表 ----------
const products = ref<ProductVO[]>([])
const loading = ref(false)
const finished = ref(false)
const keyword = ref('')
const status = ref('')
const page = ref(1)
const total = ref(0)
const dialog = ref(false)
const saving = ref(false)
const skuCountCache = ref<Record<number, number>>({})

const categoryTree = ref<CategoryVO[]>([])
const adminBrandList = ref<BrandVO[]>([])
const categoryPath = ref<number[]>([])
const cascaderProps = { value: 'id', label: 'name', children: 'children', emitPath: true } as const

const emptyForm = (): Partial<ProductVO> => ({
  name: '', price: 0, stock: 0,
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
    for (const p of result.records) void loadSkuCount(p.id)
    if (result.records.length === 0 || products.value.length >= result.total) {
      finished.value = true
    } else {
      page.value++
    }
  } finally {
    loading.value = false
  }
}

async function loadSkuCount(productId: number) {
  try {
    const list = await apiAdminSkus(productId)
    skuCountCache.value = { ...skuCountCache.value, [productId]: list.length }
  } catch {
    /* 忽略 */
  }
}

function loadMore() {
  load()
}

function openCreate() {
  Object.assign(form, emptyForm())
  categoryPath.value = []
  dialog.value = true
}

async function save() {
  if (!form.name) {
    ElMessage.warning('请填写商品名')
    return
  }
  if (!form.brandId) {
    ElMessage.warning('请选择品牌（品牌在「品牌」页签维护）')
    return
  }
  if (!categoryPath.value.length) {
    ElMessage.warning('请选择分类（分类在「分类」页签维护）')
    return
  }
  const brand = adminBrandList.value.find((b) => b.id === form.brandId)
  saving.value = true
  try {
    await apiAdminProductCreate({
      ...form,
      brandId: form.brandId,
      categoryId: categoryPath.value[categoryPath.value.length - 1],
      brand: brand?.name,
    })
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

// ---------- SKU 管理 ----------
const skuDialog = ref(false)
const skuSaving = ref(false)
const skuProduct = ref<ProductVO | null>(null)
const skuList = ref<SkuVO[]>([])
const skuForm = reactive({ spText: '', price: 0, stock: 0 })

/** "颜色:黑色,容量:256G" -> sp_data JSON */
function textToSp(text: string): string | null {
  const entries = text.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
    .map((s) => {
      const idx = s.indexOf(':') >= 0 ? s.indexOf(':') : s.indexOf('：')
      if (idx <= 0 || idx === s.length - 1) return null
      return { key: s.slice(0, idx).trim(), value: s.slice(idx + 1).trim() }
    })
  if (!entries.length || entries.some((e) => e === null)) return null
  return JSON.stringify(entries)
}

function spText(spData?: string): string {
  try {
    const arr = JSON.parse(spData || '[]') as { key: string; value: string }[]
    return arr.map((e) => `${e.key}:${e.value}`).join('，')
  } catch {
    return spData || ''
  }
}

function openSkus(row: ProductVO) {
  skuProduct.value = row
  skuForm.spText = ''
  skuForm.price = 0
  skuForm.stock = 0
  skuDialog.value = true
  loadSkus(row.id)
}

async function loadSkus(productId: number) {
  skuList.value = await apiAdminSkus(productId)
}

async function createSku() {
  if (!skuProduct.value) return
  const sp = textToSp(skuForm.spText)
  if (!sp) {
    ElMessage.warning('规格格式：属性名:属性值，多属性用逗号分隔')
    return
  }
  skuSaving.value = true
  try {
    await apiAdminSkuCreate(skuProduct.value.id, {
      spData: sp, price: skuForm.price, stock: skuForm.stock, status: 'ENABLE',
    })
    ElMessage.success('规格已添加，商品库存与起价已同步')
    await loadSkus(skuProduct.value.id)
    loadSkuCount(skuProduct.value.id)
    reload()
  } catch {
    // 拦截器已提示
  } finally {
    skuSaving.value = false
  }
}

async function toggleSkuStatus(row: SkuVO) {
  if (!skuProduct.value) return
  await apiAdminSkuUpdate(skuProduct.value.id, row.id, {
    status: row.status === 'ENABLE' ? 'DISABLE' : 'ENABLE',
  })
  await loadSkus(skuProduct.value.id)
  reload()
}

async function removeSku(row: SkuVO) {
  if (!skuProduct.value) return
  await apiAdminSkuDelete(skuProduct.value.id, row.id)
  ElMessage.success('规格已删除')
  await loadSkus(skuProduct.value.id)
  loadSkuCount(skuProduct.value.id)
  reload()
}

// ---------- 分类管理 ----------
const categoryDialog = ref(false)
const categorySaving = ref(false)
const categoryForm = reactive({ parentId: 0, name: '', sort: 0, navStatus: 1 })

async function loadCatalog() {
  try {
    const [tree, brands] = await Promise.all([apiAdminCatalogCategories(), apiAdminBrands()])
    categoryTree.value = tree || []
    adminBrandList.value = brands || []
  } catch {
    // 拦截器已提示
  }
}

function openCategoryCreate(parentId = 0) {
  categoryForm.parentId = parentId
  categoryForm.name = ''
  categoryForm.sort = 0
  categoryForm.navStatus = 1
  categoryDialog.value = true
}

async function saveCategory() {
  if (!categoryForm.name.trim()) {
    ElMessage.warning('请填写分类名称')
    return
  }
  categorySaving.value = true
  try {
    await apiAdminCategoryCreate({ ...categoryForm, name: categoryForm.name.trim() })
    ElMessage.success('分类已创建')
    categoryDialog.value = false
    loadCatalog()
  } catch {
    // 拦截器已提示
  } finally {
    categorySaving.value = false
  }
}

async function toggleCategoryNav(row: CategoryVO) {
  await apiAdminCategoryUpdate(row.id, { navStatus: row.navStatus === 1 ? 0 : 1 })
  loadCatalog()
}

async function removeCategory(row: CategoryVO) {
  await apiAdminCategoryDelete(row.id)
  ElMessage.success('分类已删除')
  loadCatalog()
}

// ---------- 品牌管理 ----------
const brandDialog = ref(false)
const brandSaving = ref(false)
const brandForm = reactive({ name: '', firstLetter: '', logo: '', brandStory: '' })

async function saveBrand() {
  if (!brandForm.name.trim()) {
    ElMessage.warning('请填写品牌名称')
    return
  }
  brandSaving.value = true
  try {
    await apiAdminBrandCreate({
      ...brandForm,
      name: brandForm.name.trim(),
      firstLetter: brandForm.firstLetter.trim().toUpperCase() || undefined,
    })
    ElMessage.success('品牌已创建')
    brandDialog.value = false
    brandForm.name = ''
    brandForm.firstLetter = ''
    brandForm.logo = ''
    brandForm.brandStory = ''
    loadCatalog()
  } catch {
    // 拦截器已提示
  } finally {
    brandSaving.value = false
  }
}

async function toggleBrandStatus(row: BrandVO) {
  await apiAdminBrandUpdate(row.id, { showStatus: row.showStatus === 1 ? 0 : 1 })
  loadCatalog()
}

async function removeBrand(row: BrandVO) {
  await apiAdminBrandDelete(row.id)
  ElMessage.success('品牌已删除')
  loadCatalog()
}

// 页签切换到分类/品牌时刷新目录
watch(tab, (v) => {
  if (v === 'categories' || v === 'brands') loadCatalog()
  if (v === 'promotions') loadPromotions()
})

// ---------- 营销（券 + 秒杀） ----------
const promoTab = ref('coupons')
const couponList = ref<Array<Record<string, any>>>([])
const seckillList = ref<Array<Record<string, any>>>([])
const couponDialog = ref(false)
const seckillDialog = ref(false)
const promoSaving = ref(false)
const couponWindow = ref<[string, string] | null>(null)
const seckillWindow = ref<[string, string] | null>(null)
const couponForm = reactive<Record<string, any>>({
  name: '', discountValue: 10, minAmount: 100, totalCount: 100, validDays: 7,
})
const seckillForm = reactive<Record<string, any>>({
  productId: '', seckillPrice: 0, seckillStock: 100, seckillLimit: 1,
})

async function loadPromotions() {
  try {
    const [coupons, seckills] = await Promise.all([apiAdminCoupons(), apiAdminSeckills()])
    couponList.value = coupons || []
    seckillList.value = seckills || []
  } catch {
    // 拦截器已提示
  }
}

function fmtWindow(start?: string, end?: string): string {
  const s = (start || '').replace('T', ' ').slice(5, 16)
  const e = (end || '').replace('T', ' ').slice(5, 16)
  return `${s || '长期'} ~ ${e || '长期'}`
}

async function saveCoupon() {
  if (!couponForm.name?.trim()) {
    ElMessage.warning('请填写券名称')
    return
  }
  promoSaving.value = true
  try {
    await apiAdminCouponCreate({
      ...couponForm,
      name: couponForm.name.trim(),
      startTime: couponWindow.value?.[0] || null,
      endTime: couponWindow.value?.[1] || null,
      status: 'ENABLE',
    })
    ElMessage.success('优惠券已创建')
    couponDialog.value = false
    loadPromotions()
  } catch {
    // 拦截器已提示
  } finally {
    promoSaving.value = false
  }
}

async function toggleCoupon(row: Record<string, any>) {
  await apiAdminCouponUpdate(row.id, {
    status: row.status === 'ENABLE' ? 'DISABLE' : 'ENABLE',
  })
  loadPromotions()
}

async function removeCoupon(row: Record<string, any>) {
  await apiAdminCouponDelete(row.id)
  ElMessage.success('已删除')
  loadPromotions()
}

async function saveSeckill() {
  const productId = Number(seckillForm.productId)
  if (!productId || productId <= 0) {
    ElMessage.warning('请填写有效的商品ID')
    return
  }
  if (!seckillWindow.value) {
    ElMessage.warning('请选择活动时间窗')
    return
  }
  promoSaving.value = true
  try {
    await apiAdminSeckillCreate({
      productId,
      seckillPrice: seckillForm.seckillPrice,
      seckillStock: seckillForm.seckillStock,
      seckillLimit: seckillForm.seckillLimit,
      startTime: seckillWindow.value[0],
      endTime: seckillWindow.value[1],
      status: 'ENABLE',
    })
    ElMessage.success('秒杀活动已创建')
    seckillDialog.value = false
    loadPromotions()
  } catch {
    // 拦截器已提示
  } finally {
    promoSaving.value = false
  }
}

async function toggleSeckill(row: Record<string, any>) {
  await apiAdminSeckillUpdate(row.id, {
    status: row.status === 'ENABLE' ? 'DISABLE' : 'ENABLE',
  })
  loadPromotions()
}

async function removeSeckill(row: Record<string, any>) {
  await apiAdminSeckillDelete(row.id)
  ElMessage.success('已删除')
  loadPromotions()
}

onMounted(() => {
  load()
  loadCatalog()
})
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

.tab-hint {
  flex: 1;
  color: #909399;
  font-size: 13px;
}

.load-state {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 18px 0 24px;
}

.sku-form {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.form-hint {
  margin-left: 10px;
  color: #909399;
  font-size: 12px;
}
</style>
