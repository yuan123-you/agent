/** 全站主题（亮/暗/跟随系统）：html.dark 类 + localStorage 持久化 */
export type ThemeMode = 'light' | 'dark' | 'system'

const KEY = 'aimall-theme'

export function currentTheme(): ThemeMode {
  const v = localStorage.getItem(KEY)
  return v === 'dark' || v === 'light' || v === 'system' ? v : 'system'
}

function applyTheme(mode: ThemeMode) {
  const dark =
    mode === 'dark' ||
    (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
}

export function setTheme(mode: ThemeMode) {
  localStorage.setItem(KEY, mode)
  applyTheme(mode)
}

/** 循环切换：system -> light -> dark -> system */
export function cycleTheme(): ThemeMode {
  const order: ThemeMode[] = ['system', 'light', 'dark']
  const next = order[(order.indexOf(currentTheme()) + 1) % order.length]
  setTheme(next)
  return next
}

/** 跟随系统时监听系统切换 */
export function initTheme() {
  applyTheme(currentTheme())
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (currentTheme() === 'system') applyTheme('system')
  })
}
