export interface RegionOption {
  value: string
  label: string
  children?: RegionOption[]
}

export function composeAddress(regionLabels: string[], detailAddress: string): string {
  return [...regionLabels, detailAddress.trim()].filter(Boolean).join('')
}

export function normalizeGeocode(data: Record<string, unknown>) {
  const province = String(data.principalSubdivision || '').trim()
  const city = String(data.city || '').trim()
  const locality = String(data.locality || '').trim()
  return { province, city, district: locality && locality !== city && locality !== province ? locality : '' }
}

export function labelsForCodes(options: RegionOption[], codes: string[]): string[] {
  const labels: string[] = []
  let level = options
  for (const code of codes) {
    const option = level.find((item) => item.value === code)
    if (!option) break
    labels.push(option.label)
    level = option.children || []
  }
  return labels
}

export function codesForLabels(options: RegionOption[], labels: string[]): string[] {
  const codes: string[] = []
  let level = options
  for (const label of labels.filter(Boolean)) {
    const normalized = label.replace(/省|市|自治区|壮族|回族|维吾尔/g, '')
    const option = level.find((item) => item.label === label || item.label.includes(normalized) || label.includes(item.label.replace(/省|市/g, '')))
    if (!option) break
    codes.push(option.value)
    level = option.children || []
  }
  return codes
}
