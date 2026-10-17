import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory, type Router } from 'vue-router'
import ElementPlus from 'element-plus'
import LoginView from './LoginView.vue'

let app: App | undefined
let router: Router | undefined
let container: HTMLDivElement | undefined

afterEach(() => {
  app?.unmount()
  router?.options.history.destroy()
  container?.remove()
  vi.restoreAllMocks()
})

async function mountPage(register: boolean, hasPreviousPage: boolean) {
  localStorage.clear()
  window.history.replaceState(null, '', '/')
  router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/', component: { template: '<div>商城首页</div>' } },
      { path: '/products', component: { template: '<div>商品列表</div>' } },
      { path: '/login', component: LoginView },
    ],
  })
  if (hasPreviousPage) await router.push('/products?category=phones')
  await router.push('/login')
  await router.isReady()
  // jsdom shares browser history across tests; model a fresh tab explicitly.
  if (!hasPreviousPage) vi.spyOn(window.history, 'length', 'get').mockReturnValue(1)
  container = document.createElement('div')
  document.body.append(container)
  app = createApp(LoginView).use(createPinia()).use(router).use(ElementPlus)
  app.mount(container)
  if (register) {
    const tab = Array.from(container.querySelectorAll<HTMLElement>('[role="tab"]'))
      .find(element => element.textContent === '注册')!
    tab.click()
    await nextTick()
    expect(tab.getAttribute('aria-selected')).toBe('true')
  }
  return container
}

describe.each([false, true])('auth back button (registration: %s)', register => {
  it('returns to the previous page including its query', async () => {
    const page = await mountPage(register, true)
    const button = Array.from(page.querySelectorAll('button'))
      .find(element => element.textContent?.includes('返回'))
    expect(button).toBeDefined()
    button!.click()
    await vi.waitFor(() => {
      expect(router!.currentRoute.value.fullPath).toBe('/products?category=phones')
    })
  })

  it('falls back to the mall homepage when there is no previous page', async () => {
    const page = await mountPage(register, false)
    const button = Array.from(page.querySelectorAll('button'))
      .find(element => element.textContent?.includes('返回'))
    expect(button).toBeDefined()
    button!.click()
    await vi.waitFor(() => {
      expect(router!.currentRoute.value.path).toBe('/')
    })
  })
})
