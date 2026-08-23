<template>
  <div class="login-page">
    <el-card class="login-card">
      <div class="brand">
        <h2>AI Mall</h2>
        <p>智能电商平台 · AI 购物助手</p>
      </div>
      <el-tabs v-model="tab">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" label-position="top" @keyup.enter="doLogin">
            <el-form-item label="用户名">
              <el-input v-model="loginForm.username" placeholder="如 customer01" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="loginForm.password" type="password" show-password placeholder="密码" />
            </el-form-item>
            <el-button type="primary" class="submit" :loading="loading" @click="doLogin">登 录</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-tabs v-model="registrationKind" class="registration-kind">
            <el-tab-pane label="买家注册" name="CUSTOMER" />
            <el-tab-pane label="卖家注册" name="MERCHANT" />
          </el-tabs>
          <el-form :model="regForm" label-position="top">
            <el-form-item label="用户名">
              <el-input v-model="regForm.username" placeholder="4~32位字母数字下划线" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="regForm.password" type="password" show-password placeholder="6~32位" />
            </el-form-item>
            <el-form-item label="昵称">
              <el-input v-model="regForm.nickname" placeholder="昵称" />
            </el-form-item>
            <el-form-item label="手机号（可选）">
              <el-input v-model="regForm.phone" placeholder="手机号" />
            </el-form-item>
            <el-form-item v-if="registrationKind === 'MERCHANT'" label="店铺名称">
              <el-input v-model="regForm.shopName" placeholder="店铺名称" />
            </el-form-item>
            <el-button type="primary" class="submit" :loading="loading" @click="doRegister">注 册</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      <el-alert type="info" :closable="false" class="tips"
        title="演示账号：customer01 买家 / merchant01 卖家 / agent01 客服 / admin 管理员，密码均为 123456" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { buildRegistrationPayload, type RegistrationKind, validateRegistration } from './auth/registration'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const tab = ref('login')
const loading = ref(false)
const loginForm = reactive({ username: '', password: '' })
const registrationKind = ref<RegistrationKind>('CUSTOMER')
const regForm = reactive({ username: '', password: '', nickname: '', phone: '', shopName: '' })

async function doLogin() {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login({ ...loginForm })
    ElMessage.success('登录成功')
    router.push((route.query.redirect as string) || auth.homeRoute())
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function doRegister() {
  const errors = validateRegistration(registrationKind.value, regForm)
  if (errors.length) {
    ElMessage.warning(errors[0])
    return
  }
  loading.value = true
  try {
    if (registrationKind.value === 'MERCHANT') {
      await auth.registerMerchant(buildRegistrationPayload('MERCHANT', regForm))
    } else {
      await auth.registerCustomer(buildRegistrationPayload('CUSTOMER', regForm))
    }
    ElMessage.success('注册成功，请登录')
    tab.value = 'login'
    loginForm.username = regForm.username
    loginForm.password = ''
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e0eaff 0%, #f5f7fa 100%);
}

.login-card {
  width: 400px;
  padding: 8px 12px;
}

.brand {
  text-align: center;
  margin-bottom: 8px;
}

.brand h2 {
  margin: 0;
  color: var(--el-color-primary);
}

.brand p {
  margin: 4px 0 12px;
  color: #909399;
  font-size: 13px;
}

.submit {
  width: 100%;
  margin-top: 4px;
}

.registration-kind {
  margin-bottom: 8px;
}

.tips {
  margin-top: 12px;
}
</style>
