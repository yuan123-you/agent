<template>
  <div
    class="page"
    v-infinite-scroll="loadMore"
    :infinite-scroll-disabled="loading || finished"
    :infinite-scroll-distance="60"
  >
    <div class="toolbar">
      <h3 class="page-title">用户管理（{{ total }}）</h3>
      <el-input v-model="keyword" placeholder="搜索用户名/昵称" clearable style="width: 220px"
        @keyup.enter="reload" @clear="reload" />
      <el-select v-model="role" style="width: 130px" @change="reload">
        <el-option label="全部角色" value="" />
        <el-option label="买家" value="CUSTOMER" />
        <el-option label="客服" value="AGENT" />
        <el-option label="管理员" value="ADMIN" />
      </el-select>
    </div>

    <el-table v-loading="loading && users.length === 0" :data="users" border stripe>
      <el-table-column prop="userId" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" width="130" />
      <el-table-column prop="nickname" label="昵称" width="120" />
      <el-table-column label="角色" width="100">
        <template #default="{ row }">{{ roleText(row.role) }}</template>
      </el-table-column>
      <el-table-column prop="phone" label="手机号" width="140" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'ACTIVE' ? 'success' : 'danger'" size="small">
            {{ row.status === 'ACTIVE' ? '正常' : '已禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="注册时间" width="160" />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <template v-if="row.role !== 'ADMIN'">
            <el-button size="small" :type="row.status === 'ACTIVE' ? 'warning' : 'success'" @click="toggleStatus(row)">
              {{ row.status === 'ACTIVE' ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" @click="changeRole(row)">{{ row.role === 'AGENT' ? '转为买家' : '转为客服' }}</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="loading" class="load-state">加载中...</div>
    <div v-else-if="finished && users.length > 0" class="load-state">— 没有更多了 —</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiAdminUserUpdate, apiAdminUsers } from '@/api'
import type { UserInfo } from '@/types/api'

type UserRow = UserInfo & { status: string }

const users = ref<UserRow[]>([])
const loading = ref(false)
const finished = ref(false)
const keyword = ref('')
const role = ref('')
const page = ref(1)
const total = ref(0)

function reload() {
  page.value = 1
  finished.value = false
  users.value = []
  load()
}

/** 懒加载：滚动到底部自动追加下一页 */
async function load() {
  if (loading.value || finished.value) return
  loading.value = true
  try {
    const result = await apiAdminUsers({
      page: page.value, size: 20,
      ...(keyword.value.trim() ? { keyword: keyword.value.trim() } : {}),
      ...(role.value ? { role: role.value } : {}),
    })
    users.value.push(...(result.records as UserRow[]))
    total.value = result.total
    if (result.records.length === 0 || users.value.length >= result.total) {
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

async function toggleStatus(row: UserRow) {
  const target = row.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE'
  await apiAdminUserUpdate(row.userId, { status: target })
  ElMessage.success(target === 'ACTIVE' ? '已启用' : '已禁用')
  reload()
}

async function changeRole(row: UserRow) {
  const target = row.role === 'AGENT' ? 'CUSTOMER' : 'AGENT'
  await apiAdminUserUpdate(row.userId, { role: target })
  ElMessage.success(target === 'AGENT' ? '已转为客服' : '已转为买家')
  reload()
}

function roleText(r: string): string {
  return { ADMIN: '管理员', AGENT: '人工客服', CUSTOMER: '买家' }[r] || r
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

.load-state {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 18px 0 24px;
}
</style>
