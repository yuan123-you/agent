import { ref } from 'vue'
import { defaultMallConfig, type MallConfig, type MallThemeConfig } from '@/config/mall.config'

const config = ref<MallConfig>({ ...defaultMallConfig })

export function applyThemePreset(presetKey: string) {
  const preset = config.value.theme.presets[presetKey]
  if (!preset) return
  config.value.theme.activeTheme = presetKey as any
  const root = document.documentElement
  if (typeof root !== 'undefined' && root.style) {
    root.style.setProperty('--mall-primary', preset.primaryColor)
    root.style.setProperty('--mall-gradient', preset.primaryGradient)
    root.style.setProperty('--mall-price', preset.priceColor)
    root.style.setProperty('--mall-radius', preset.radius)
    root.style.setProperty('--mall-container', preset.containerWidth)
  }
}

export function initMallTheme() {
  applyThemePreset(config.value.theme.activeTheme)
}

export function useMallConfig() {
  return {
    config,
    applyThemePreset,
    initMallTheme,
  }
}
