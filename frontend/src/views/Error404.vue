<template>
  <div class="error-page">
    <h1>404</h1>
    <p>页面不存在（链接可能已失效）</p>
    <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
  </div>
</template>

<style scoped>
.error-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.error-page h1 {
  font-size: 64px;
  color: #c0c4cc;
  margin: 0;
}
</style>
