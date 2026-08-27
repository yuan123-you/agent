import { codesForLabels, labelsForCodes, type RegionOption } from '@/components/address/addressForm'

export const MAX_CUSTOM_PRODUCT_INFO = 5

export interface CustomProductInfo {
  name: string
  content: string
}

export function parseCustomProductInfo(raw?: string): CustomProductInfo[] {
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') return []
    return Object.entries(parsed)
      .filter(([, content]) => ['string', 'number', 'boolean'].includes(typeof content))
      .slice(0, MAX_CUSTOM_PRODUCT_INFO)
      .map(([name, content]) => ({ name, content: String(content) }))
  } catch {
    return []
  }
}

export function validateCustomProductInfo(entries: CustomProductInfo[]): string | undefined {
  if (entries.length > MAX_CUSTOM_PRODUCT_INFO) return `最多只能添加${MAX_CUSTOM_PRODUCT_INFO}项商品信息`
  const completed = entries.filter(({ name, content }) => name.trim() || content.trim())
  if (completed.some(({ name, content }) => !name.trim() || !content.trim())) {
    return '请完整填写选项名称和选项内容'
  }
  const names = completed.map(({ name }) => name.trim())
  if (new Set(names).size !== names.length) return '选项名称不能重复'
}

export function serializeCustomProductInfo(entries: CustomProductInfo[]): string {
  const values = entries
    .filter(({ name, content }) => name.trim() && content.trim())
    .map(({ name, content }) => [name.trim(), content.trim()])
  return values.length ? JSON.stringify(Object.fromEntries(values)) : ''
}

export function isCompleteProductLocation(codes: string[]): boolean {
  return codes.length === 3
}

export function locationValueForCodes(options: RegionOption[], codes: string[]): string {
  return labelsForCodes(options, codes).join(' / ')
}

export function locationCodesForValue(options: RegionOption[], value?: string): string[] {
  if (!value) return []
  const separated = value.split(/\s*[/／]\s*/).filter(Boolean)
  if (separated.length > 1) return codesForLabels(options, separated)

  const codes: string[] = []
  let remaining = value.replace(/\s/g, '')
  let level = options
  while (remaining && level.length) {
    const option = level.find((item) => remaining.startsWith(item.label.replace(/\s/g, '')))
    if (!option) break
    codes.push(option.value)
    remaining = remaining.slice(option.label.replace(/\s/g, '').length)
    level = option.children || []
  }
  return codes
}
