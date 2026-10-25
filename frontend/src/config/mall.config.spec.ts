import { describe, it, expect } from 'vitest'
import { defaultMallConfig } from './mall.config'
import { applyThemePreset, useMallConfig } from '@/composables/useMallConfig'

describe('Mall Configuration & Theme Preset System', () => {
  it('provides complete site identity and metadata', () => {
    expect(defaultMallConfig.site.name).toBe('AI Mall')
    expect(defaultMallConfig.site.slogan).toBeTruthy()
    expect(defaultMallConfig.site.logoBadge).toBe('AI')
    expect(defaultMallConfig.site.supportPhone).toBeTruthy()
    expect(defaultMallConfig.site.copyright).toBeTruthy()
    expect(defaultMallConfig.site.icp).toBeTruthy()
  })

  it('contains all 5 essential theme presets for template variety', () => {
    const presets = defaultMallConfig.theme.presets
    expect(presets.minimal).toBeDefined()
    expect(presets.tech).toBeDefined()
    expect(presets.classic).toBeDefined()
    expect(presets.emerald).toBeDefined()
    expect(presets.amber).toBeDefined()

    for (const key of ['minimal', 'tech', 'classic', 'emerald', 'amber']) {
      expect(presets[key].primaryColor).toMatch(/^#/)
      expect(presets[key].radius).toBeTruthy()
      expect(presets[key].containerWidth).toBeTruthy()
    }
  })

  it('supports modular feature toggles for flexible floor layouts', () => {
    const f = defaultMallConfig.features
    expect(typeof f.enableTrustBar).toBe('boolean')
    expect(typeof f.enableBentoPromo).toBe('boolean')
    expect(typeof f.enableFlashSale).toBe('boolean')
    expect(typeof f.enableCoupons).toBe('boolean')
    expect(typeof f.enableAiAssistantPromo).toBe('boolean')
    expect(typeof f.enableFloorGoods).toBe('boolean')
    expect(typeof f.enableBrandWall).toBe('boolean')
  })

  it('provides structured hero slides and bento promo cards', () => {
    expect(defaultMallConfig.heroSlides.length).toBeGreaterThanOrEqual(2)
    expect(defaultMallConfig.bentoCards.length).toBeGreaterThanOrEqual(4)
    expect(defaultMallConfig.brandPartners.length).toBeGreaterThanOrEqual(6)
    expect(defaultMallConfig.footerColumns.length).toBeGreaterThanOrEqual(4)
  })

  it('applies theme presets and updates document CSS variables', () => {
    const { config } = useMallConfig()
    applyThemePreset('tech')
    expect(config.value.theme.activeTheme).toBe('tech')
    expect(document.documentElement.style.getPropertyValue('--mall-primary')).toBe(
      defaultMallConfig.theme.presets.tech.primaryColor
    )

    applyThemePreset('minimal')
    expect(config.value.theme.activeTheme).toBe('minimal')
    expect(document.documentElement.style.getPropertyValue('--mall-primary')).toBe(
      defaultMallConfig.theme.presets.minimal.primaryColor
    )
  })
})
