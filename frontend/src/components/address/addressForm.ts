export interface RegionOption {
  value: string
  label: string
  children?: RegionOption[]
}

interface GeocodeItem {
  name?: unknown
  description?: unknown
}

export interface NormalizedGeocode {
  province: string
  city: string
  district: string
  detailAddress: string
}

export function composeAddress(regionLabels: string[], detailAddress: string): string {
  return [...regionLabels, detailAddress.trim()].filter(Boolean).join('')
}

function geocodeItems(value: unknown): GeocodeItem[] {
  return Array.isArray(value) ? value.filter((item): item is GeocodeItem => Boolean(item) && typeof item === 'object') : []
}

export function normalizeGeocode(data: Record<string, unknown>): NormalizedGeocode {
  const province = String(data.principalSubdivision || '').trim()
  const city = String(data.city || '').trim()
  const locality = String(data.locality || '').trim()
  const localityInfo = data.localityInfo && typeof data.localityInfo === 'object'
    ? data.localityInfo as Record<string, unknown>
    : {}
  const administrative = geocodeItems(localityInfo.administrative)
  const informative = geocodeItems(localityInfo.informative)

  const administrativeDistrict = administrative.find((item) => {
    const name = String(item.name || '').trim()
    const description = String(item.description || '').toLowerCase()
    return name !== province && name !== city
      && (description.includes('district') || description.includes('county') || /[区县旗]$/.test(name))
  })
  const district = String(administrativeDistrict?.name || (
    locality !== city && locality !== province && /[区县旗]$/.test(locality) ? locality : ''
  )).trim()

  const details = [
    ...administrative
      .filter((item) => /locality|town|village|neighbou?rhood|suburb/i.test(String(item.description || '')))
      .map((item) => String(item.name || '').trim()),
    locality,
    ...informative
      .filter((item) => !/postcode|continent|time zone/i.test(String(item.description || '')))
      .map((item) => String(item.name || '').trim()),
  ].filter((name, index, values) =>
    Boolean(name)
    && name !== province && name !== city && name !== district && name !== '中国'
    && values.indexOf(name) === index,
  )

  return { province, city, district, detailAddress: details.join('') }
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

function regionKey(label: string): string {
  return label.replace(/\s|特别行政区|自治区|自治州|壮族|回族|维吾尔族?|蒙古族?|省|市$/g, '')
}

export function codesForLabels(options: RegionOption[], labels: string[]): string[] {
  const codes: string[] = []
  let level = options
  for (const label of labels.filter(Boolean)) {
    const key = regionKey(label)
    const option = level.find((item) => {
      const itemKey = regionKey(item.label)
      return item.label === label || (Boolean(key) && Boolean(itemKey) && (itemKey === key || itemKey.includes(key) || key.includes(itemKey)))
    }) || level.find((item) => item.label === '市辖区' && /市$/.test(label))
    if (!option) break
    codes.push(option.value)
    level = option.children || []
  }
  return codes
}
