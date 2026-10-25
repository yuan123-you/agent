<template>
  <div class="page addresses-page">
    <div class="page-header-row">
      <button class="translucent-circle-back" title="返回" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
      </button>
      <h3 class="page-title">收货地址管理</h3>
    </div>
    <AddressBook />
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import AddressBook from '@/components/address/AddressBook.vue'

const router = useRouter()
function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/profile')
}
</script>

<style scoped>
.addresses-page {
  width: min(760px, calc(100% - 32px));
  margin: 16px auto;
}

@media (max-width: 600px) {
  .addresses-page {
    width: 100%;
    margin: 0 auto;
    padding: 10px;
    box-sizing: border-box;
  }
}
</style>

