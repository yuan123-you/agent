import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import AiTraceView from './AiTraceView.vue'
const api = vi.hoisted(() => ({ list: vi.fn(), detail: vi.fn(), benchmark: vi.fn() }))
vi.mock('@/api/aiTraces', () => ({ apiAiTraces: api.list, apiAiTrace: api.detail, apiAiBenchmark: api.benchmark }))
let app: App, host: HTMLDivElement
const row = { traceId:'run-1', conversationId:7, userId:1, status:'SUCCESS', inputPreview:'推荐一款手机', modelCalls:1, totalTokens:null, stageCount:2, durationMs:1200, createdAt:'2026-10-29T12:00:00' }
const detail = { ...row, stages:[
  { id:'n1', name:'intent_router', kind:'node', status:'SUCCESS', startMs:0, durationMs:2, input:{message:'推荐手机'}, output:{intent:'PRODUCT_CONSULT'} },
  { id:'m1', name:'ChatModel', kind:'model', model:'qwen', status:'SUCCESS', startMs:4, durationMs:900, input:{query:'真实输入'}, output:{content:'<script>alert(1)</script>'} },
], omittedStages:0 }
const flush = async () => { for (let i=0;i<12;i++) await nextTick() }
async function mount() {
  host=document.createElement('div'); document.body.append(host); app=createApp(AiTraceView); app.mount(host); await flush()
}
async function click(label: string) {
  const b=[...host.querySelectorAll('button')].find(b=>b.textContent?.trim()===label)
  expect(b, label).toBeTruthy(); b!.click(); await flush()
}
beforeEach(()=>{ vi.resetAllMocks(); api.list.mockResolvedValue({records:[row],total:1,page:1,size:20}); api.detail.mockResolvedValue(detail); api.benchmark.mockResolvedValue({overallScore:99.67,overallPassRate:1.0,totalCases:60,scorecards:[{category:'PRE_SALES',categoryName:'售前导购与选型',averageScore:98.0,passRate:1.0,passedCases:10,totalCases:10}]}) })
afterEach(()=>{app?.unmount(); host?.remove()})
describe('admin AI trace console',()=>{
  it('lists actual turns and distinguishes unknown token usage from zero',async()=>{
    await mount(); expect(host.textContent).toContain('推荐一款手机'); expect(host.textContent).toContain('未返回'); expect(api.list).toHaveBeenCalledTimes(1)
  })
  it('opens a timeline and renders trace payload as text, never executable HTML',async()=>{
    await mount(); await click('查看链路'); expect(api.detail).toHaveBeenCalledWith('run-1')
    const stage=host.querySelector<HTMLButtonElement>('[data-stage-id="m1"]')!; stage.click(); await flush()
    expect(host.textContent).toContain('真实输入'); expect(host.textContent).toContain('<script>alert(1)</script>'); expect(host.querySelector('script')).toBeNull()
  })
  it('sends explicit filters and resets pagination',async()=>{
    await mount(); const input=host.querySelector<HTMLInputElement>('[name="conversationId"]')!; input.value='7'; input.dispatchEvent(new Event('input')); await click('查询')
    expect(api.list).toHaveBeenLastCalledWith(expect.objectContaining({conversationId:7,page:1}))
  })
  it('provides empty and failed load states without invented trace data',async()=>{
    api.list.mockResolvedValueOnce({records:[],total:0,page:1,size:20}); await mount(); expect(host.textContent).toContain('暂无链路记录')
    api.list.mockRejectedValueOnce(new Error('offline')); await click('刷新列表'); expect(host.textContent).toContain('链路列表加载失败')
  })
  it('does not retain another trace detail when a new detail fails',async()=>{
    await mount(); await click('查看链路'); api.detail.mockRejectedValueOnce(new Error('offline')); await click('刷新详情')
    expect(host.textContent).toContain('链路详情加载失败'); expect(host.querySelector('[data-stage-id="m1"]')).toBeNull()
  })
})
