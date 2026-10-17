import { afterEach, describe, expect, it } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import LoginView from '../LoginView.vue'

let app: App | undefined
let host: HTMLDivElement

afterEach(() => {
  app?.unmount()
  host?.remove()
})

describe('registration form', () => {
  it('shows two buyer inputs and adds only a shop name for merchants', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: LoginView }],
    })
    await router.push('/')
    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp(LoginView).use(createPinia()).use(router).use(ElementPlus)
    app.mount(host)
    await nextTick()
    const clickTab = async (text: string) => {
      const tab = [...host.querySelectorAll<HTMLElement>('[role="tab"]')]
        .find(element => element.textContent?.trim() === text)!
      tab.click()
      await nextTick()
    }
    await clickTab('注册')
    const registration = host.querySelector('#pane-register')!
    const labels = () => [...registration.querySelectorAll('.el-form-item__label')]
      .map(element => element.textContent)
    expect(labels()).toEqual(['用户名', '密码'])
    expect(registration.querySelectorAll('input')).toHaveLength(2)
    await clickTab('卖家注册')
    expect(labels()).toEqual(['用户名', '密码', '店铺名称'])
    expect(registration.querySelectorAll('input')).toHaveLength(3)
  })
})
