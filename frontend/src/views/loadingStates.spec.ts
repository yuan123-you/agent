import { describe, expect, it } from 'vitest'

const sources = import.meta.glob(['./**/*.vue', '../components/**/*.vue'], {
  eager: true, query: '?raw', import: 'default',
}) as Record<string, string>

describe('loading presentation across all pages and nested panels', () => {
  it('never uses a bare paragraph or load-state div as a loading indicator', () => {
    const offenders = Object.entries(sources).filter(([, source]) =>
      /<(?:p|div)\b[^>]*>\s*(?:商品|规格|评价)?加载中(?:\.{3}|…)?\s*<\//.test(source),
    ).map(([file]) => file)
    expect(offenders).toEqual([])
  })

  it('provides layout-aware skeletons for previously blank or overlay-only data pages', () => {
    for (const file of [
      './CartView.vue', './OrderDetailView.vue', './SeckillView.vue',
      './CouponCenterView.vue', './MyCouponsView.vue',
      './admin/DashboardView.vue', './admin/StatsView.vue',
      './workbench/WorkbenchView.vue', './workbench/WorkbenchConvView.vue',
      '../components/address/AddressBook.vue', '../components/address/CheckoutAddressPicker.vue',
      '../components/mall/CouponPicker.vue', '../components/product/QuickViewModal.vue',
    ]) expect(sources[file], file).toContain('<LoadingState')
  })

  it('uses a centered spinner for unknown document formats instead of an overlay on an empty box', () => {
    expect(sources['./admin/KbManageView.vue']).toMatch(/<LoadingState[^>]*previewLoading[^>]*variant="spinner"[^>]*full-page/)
  })
})
