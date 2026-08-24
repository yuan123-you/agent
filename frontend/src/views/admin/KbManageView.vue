<template>
  <el-scrollbar class="page-scroll" :distance="60" @end-reached="direction => direction === 'bottom' && loadMore()">
    <div class="page">
    <div class="toolbar">
      <h3 class="page-title">知识库管理（{{ total }}）</h3>
      <el-select v-model="status" style="width: 130px" @change="reload">
        <el-option label="全部状态" value="" />
        <el-option label="处理中" value="PROCESSING" />
        <el-option label="已生效" value="ACTIVE" />
        <el-option label="已停用" value="DISABLED" />
        <el-option label="失败" value="FAILED" />
      </el-select>
      <el-button type="primary" @click="uploadDialog = true">上传文档</el-button>
    </div>

    <el-table v-loading="loading && docs.length === 0" :data="docs" border stripe>
      <el-table-column prop="docId" label="ID" width="70" />
      <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">{{ typeText(row.docType) }}</template>
      </el-table-column>
      <el-table-column prop="fileFormat" label="格式" width="80" />
      <el-table-column prop="chunkCount" label="分块数" width="90" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.status === 'PROCESSING' || row.status === 'PENDING'" size="small" type="warning">
            <el-icon class="is-loading"><Loading /></el-icon> 处理中
          </el-tag>
          <el-tag v-else-if="row.status === 'ACTIVE'" size="small" type="success">已生效</el-tag>
          <el-tag v-else-if="row.status === 'DISABLED'" size="small" type="info">已停用</el-tag>
          <el-tooltip v-else :content="row.failReason || '摄取失败'">
            <el-tag size="small" type="danger">失败</el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="上传时间" width="160" />
      <el-table-column label="操作" width="290" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click="openPreview(row)">查看</el-button>
          <el-button v-if="row.status === 'ACTIVE'" size="small" type="warning" @click="toggle(row, 'DISABLED')">
            停用
          </el-button>
          <el-button v-if="row.status === 'DISABLED' || row.status === 'FAILED'" size="small" type="success"
            @click="reindex(row)">
            重建索引
          </el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="loading" class="load-state">加载中...</div>
    <div v-else-if="finished && docs.length > 0" class="load-state">— 没有更多了 —</div>

    <!-- 文档预览弹窗 -->
    <el-dialog v-model="previewDialog" :title="previewTitle" width="80%" top="5vh" @closed="clearPreview">
      <div v-loading="previewLoading" class="preview-body">
        <iframe
          v-if="preview?.kind === 'pdf'"
          :src="preview.url"
          class="preview-pdf"
          title="知识库 PDF 文档预览"
        />
        <pre v-else-if="preview?.kind === 'text'" class="preview-text">{{ preview.content }}</pre>
      </div>
    </el-dialog>

    <!-- 上传弹窗 -->
    <el-dialog v-model="uploadDialog" title="上传知识文档" width="480px">
      <el-form label-width="90px">
        <el-form-item label="文档标题">
          <el-input v-model="uploadForm.title" placeholder="如：退换货政策" />
        </el-form-item>
        <el-form-item label="关联商品">
          <el-select v-model="uploadForm.productId" placeholder="平台通用（不选）" clearable filterable>
            <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="文档类型">
          <el-select v-model="uploadForm.docType">
            <el-option label="FAQ（常见问题）" value="FAQ" />
            <el-option label="INTRO（商品介绍）" value="INTRO" />
            <el-option label="POLICY（平台政策）" value="POLICY" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <input type="file" accept=".pdf,.md,.txt" @change="onFileChange" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">上传并摄取</el-button>
      </template>
    </el-dialog>
    </div>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import {
  apiAdminProducts, apiKbContent, apiKbDelete, apiKbDocs, apiKbReindex, apiKbToggle, apiKbUpload,
} from '@/api'
import type { KbDocVO, ProductVO } from '@/types/api'
import { releaseKbPreview, toKbPreview } from './kbPreview'
import type { KbPreview } from './kbPreview'

const docs = ref<KbDocVO[]>([])
const products = ref<ProductVO[]>([])
const loading = ref(false)
const finished = ref(false)
const status = ref('')
const page = ref(1)
const total = ref(0)
const uploadDialog = ref(false)
const uploading = ref(false)
const previewDialog = ref(false)
const previewLoading = ref(false)
const previewTitle = ref('文档预览')
const preview = ref<KbPreview | null>(null)
const file = ref<File | null>(null)

const uploadForm = reactive({
  title: '',
  productId: undefined as number | undefined,
  docType: 'FAQ',
})

let pollTimer: number | undefined

function reload() {
  page.value = 1
  finished.value = false
  docs.value = []
  load()
}

/** 懒加载：滚动到底部自动追加下一页 */
async function load() {
  if (loading.value || finished.value) return
  loading.value = true
  try {
    const result = await apiKbDocs({
      page: page.value, size: 20,
      ...(status.value ? { status: status.value } : {}),
    })
    docs.value.push(...result.records)
    total.value = result.total
    if (result.records.length === 0 || docs.value.length >= result.total) {
      finished.value = true
    } else {
      page.value++
    }
    schedulePoll()
  } finally {
    loading.value = false
  }
}

function loadMore() {
  load()
}

function schedulePoll() {
  const hasProcessing = docs.value.some((d) => ['PENDING', 'PROCESSING'].includes(d.status))
  if (hasProcessing && !pollTimer) {
    pollTimer = window.setInterval(async () => {
      const still = docs.value.some((d) => ['PENDING', 'PROCESSING'].includes(d.status))
      if (!still) {
        if (pollTimer) window.clearInterval(pollTimer)
        pollTimer = undefined
      }
      const result = await apiKbDocs({
        page: 1, size: Math.max(20, docs.value.length),
        ...(status.value ? { status: status.value } : {}),
      })
      docs.value = result.records
    }, 3000)
  }
}

function onFileChange(e: Event) {
  file.value = (e.target as HTMLInputElement).files?.[0] || null
}

async function submitUpload() {
  if (!uploadForm.title || !file.value) {
    ElMessage.warning('请填写标题并选择文件')
    return
  }
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file.value)
    formData.append('title', uploadForm.title)
    formData.append('docType', uploadForm.docType)
    if (uploadForm.productId) formData.append('productId', String(uploadForm.productId))
    await apiKbUpload(formData)
    ElMessage.success('已提交摄取，等待处理完成')
    uploadDialog.value = false
    uploadForm.title = ''
    uploadForm.productId = undefined
    file.value = null
    reload()
  } catch {
    // 拦截器已提示
  } finally {
    uploading.value = false
  }
}

async function openPreview(row: KbDocVO) {
  clearPreview()
  previewTitle.value = `查看文档：${row.title}`
  previewDialog.value = true
  previewLoading.value = true
  try {
    preview.value = await toKbPreview(await apiKbContent(row.docId), row.fileFormat)
  } catch {
    previewDialog.value = false
  } finally {
    previewLoading.value = false
  }
}

function clearPreview() {
  releaseKbPreview(preview.value)
  preview.value = null
}

async function toggle(row: KbDocVO, target: string) {
  await apiKbToggle(row.docId, target)
  ElMessage.success('已停用（检索不再命中）')
  reload()
}

async function reindex(row: KbDocVO) {
  await apiKbReindex(row.docId)
  ElMessage.success('已触发重建索引')
  reload()
}

async function remove(row: KbDocVO) {
  await ElMessageBox.confirm('删除后向量数据将同步清除，确定删除？', '提示', { type: 'warning' })
  await apiKbDelete(row.docId)
  ElMessage.success('已删除')
  reload()
}

function typeText(t: string): string {
  return { FAQ: '常见问题', INTRO: '商品介绍', POLICY: '平台政策' }[t] || t
}

onMounted(async () => {
  load()
  // 商品下拉（关联商品选择，取前 500 件足够）
  const result = await apiAdminProducts({ page: 1, size: 500 }).catch(() => null)
  if (result) products.value = result.records
})

onUnmounted(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  clearPreview()
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
}

.page-title {
  margin: 0;
  flex: 1;
}

.preview-body {
  min-height: 320px;
}

.preview-pdf {
  width: 100%;
  height: 75vh;
  border: 0;
}

.preview-text {
  min-height: 320px;
  max-height: 75vh;
  margin: 0;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: 14px/1.7 Consolas, Monaco, monospace;
}

.load-state {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 18px 0 24px;
}
</style>
