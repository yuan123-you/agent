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
      <el-button v-if="canCreateAgent(activeRole)" type="primary" @click="createDialog = true">创建客服</el-button>
    </div>

    <el-tabs v-model="activeRole" @tab-change="reload">
      <el-tab-pane v-for="tab in USER_TABS" :key="tab.role" :label="tab.label" :name="tab.role" />
    </el-tabs>

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
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" :type="row.status === 'ACTIVE' ? 'warning' : 'success'" @click="toggleStatus(row)">
            {{ row.status === 'ACTIVE' ? '禁用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="loading" class="load-state">加载中...</div>
    <div v-else-if="finished && users.length > 0" class="load-state">— 没有更多了 —</div>

    <el-dialog v-model="createDialog" title="创建客服" width="440px" @closed="resetAgentForm">
      <el-form ref="agentFormRef" :model="agentForm" :rules="agentRules" label-width="80px">
        <el-form-item label="用户名" prop="username"><el-input v-model="agentForm.username" /></el-form-item>
        <el-form-item label="密码" prop="password"><el-input v-model="agentForm.password" type="password" show-password /></el-form-item>
        <el-form-item label="昵称" prop="nickname"><el-input v-model="agentForm.nickname" /></el-form-item>
        <el-form-item label="手机号" prop="phone"><el-input v-model="agentForm.phone" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createAgent">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { apiAdminAgentCreate, apiAdminUserStatus, apiAdminUsers } from '@/api'
import type { CustomerRegistration, UserInfo } from '@/types/api'
import { USER_TABS, canCreateAgent, createLatestRequestRunner, roleText, type UserRoleTab } from './userManagement'

type UserRow = UserInfo & { status: 'ACTIVE' | 'DISABLED'; createdAt?: string }

const users = ref<UserRow[]>([])
const loading = ref(false)
const finished = ref(false)
const keyword = ref('')
const activeRole = ref<UserRoleTab>('CUSTOMER')
const page = ref(1)
const total = ref(0)
const createDialog = ref(false)
const creating = ref(false)
const agentFormRef = ref<FormInstance>()
const agentForm = reactive<CustomerRegistration>({ username: '', password: '', nickname: '', phone: '' })
const agentRules: FormRules<CustomerRegistration> = {
  username: [{ required: true, whitespace: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  nickname: [{ required: true, whitespace: true, message: '请输入昵称', trigger: 'blur' }],
}

type PageRequest = { page: number; size: number; role: UserRoleTab; keyword?: string }

const loadLatestPage = createLatestRequestRunner(
  (params: PageRequest) => apiAdminUsers(params),
  (result, request) => {
    users.value.push(...(result.records as UserRow[]))
    total.value = result.total
    if (result.records.length === 0 || users.value.length >= result.total) {
      finished.value = true
    } else {
      page.value = request.page + 1
    }
  },
  value => { loading.value = value },
)

function reload() {
  page.value = 1
  total.value = 0
  finished.value = false
  users.value = []
  load(true)
}

function load(force = false) {
  if ((!force && loading.value) || finished.value) return
  const trimmedKeyword = keyword.value.trim()
  return loadLatestPage({
    page: page.value,
    size: 20,
    role: activeRole.value,
    ...(trimmedKeyword ? { keyword: trimmedKeyword } : {}),
  })
}

function loadMore() {
  load()
}

async function toggleStatus(row: UserRow) {
  const target = row.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE'
  await apiAdminUserStatus(row.userId, target)
  ElMessage.success(target === 'ACTIVE' ? '已启用' : '已禁用')
  reload()
}

function resetAgentForm() {
  agentFormRef.value?.resetFields()
}

async function createAgent() {
  const valid = await agentFormRef.value?.validate()
  if (!valid) return
  creating.value = true
  try {
    await apiAdminAgentCreate({
      username: agentForm.username.trim(),
      password: agentForm.password,
      nickname: agentForm.nickname.trim(),
      ...(agentForm.phone?.trim() ? { phone: agentForm.phone.trim() } : {}),
    })
    ElMessage.success('客服创建成功')
    createDialog.value = false
    reload()
  } finally {
    creating.value = false
  }
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
