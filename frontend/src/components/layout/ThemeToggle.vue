<template>
  <el-tooltip :content="tip" placement="bottom">
    <el-button text class="theme-toggle" @click="toggle">
      <el-icon :size="18">
        <Monitor v-if="mode === 'system'" />
        <Sunny v-else-if="mode === 'light'" />
        <Moon v-else />
      </el-icon>
    </el-button>
  </el-tooltip>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Monitor, Moon, Sunny } from '@element-plus/icons-vue'
import { currentTheme, cycleTheme, type ThemeMode } from '@/composables/useTheme'

const mode = ref<ThemeMode>(currentTheme())
const tip = ref('主题：跟随系统')

const TIPS: Record<ThemeMode, string> = {
  system: '主题：跟随系统',
  light: '主题：浅色',
  dark: '主题：深色',
}

function toggle() {
  mode.value = cycleTheme()
  tip.value = TIPS[mode.value]
}
</script>

<style scoped>
.theme-toggle {
  padding: 6px;
}
</style>
