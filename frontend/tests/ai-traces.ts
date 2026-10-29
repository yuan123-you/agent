// Development-only visual fixture. No real user state, model, business data or API calls.
import { createApp, h } from 'vue'
import '../src/styles.css'
import request from '../src/api/request'
const params=new URLSearchParams(location.search)
const rows=[
 {traceId:'fixture-8d09a0e1-5618-4f3d-917f',conversationId:1042,userId:17,status:'SUCCESS',inputPreview:'推荐一款 3000 元以内、拍照好的手机',modelCalls:1,totalTokens:1268,stageCount:11,durationMs:1842,createdAt:'2026-10-29T13:05:24'},
 {traceId:'fixture-a4f6096c-7210-42a0-918f',conversationId:1041,userId:12,status:'DEGRADED',inputPreview:'这款商品支持七天无理由退货吗？',modelCalls:1,totalTokens:null,stageCount:14,durationMs:3290,createdAt:'2026-10-29T13:04:07'},
 {traceId:'fixture-220af715-416c-4a52-8231',conversationId:1039,userId:17,status:'FAILED',inputPreview:'帮我查一下订单物流',modelCalls:0,totalTokens:null,stageCount:0,durationMs:5011,createdAt:'2026-10-29T13:01:12'},
]
const step=(id:string,name:string,kind:string,startMs:number,durationMs:number,input:unknown,output:unknown,status='SUCCESS')=>({id,name,kind,startMs,durationMs,input,output,status})
const stages=[
 step('c','context.assemble','context',0,3,{conversationId:1042,historyCount:4},{profile:{user_name:'旅行者',assistant_name:'派蒙'},messageCount:5}),
 step('i','intent_router','node',3,2,{message:rows[0].inputPreview},{intent:'PRODUCT_CONSULT',reply_route:'agent',source:'rules'}),
 step('a','agent','node',5,8,{intent:'PRODUCT_CONSULT'},{tool_calls:[{name:'product_search',args:{category:'PHONE',max_price:3000}}]}),
 step('t','product_search','tool',13,121,{category:'PHONE',max_price:3000},{products:[{id:1,name:'示例手机 A',price:2799,link:'mall://product/1'}]}),
 {...step('m','ChatOpenAI','model',134,1685,{messages:[{role:'user',content:rows[0].inputPreview}],toolEvidence:'真实在售商品检索结果'},{content:'旅行者，按你的预算找到以下商品…'}),model:'qwen3.5:4b',usage:{input_tokens:1040,output_tokens:228,total_tokens:1268}},
 step('g','output.validate','guard',1819,2,{policyRequired:false},{citationRequired:false,changed:false,knownProductIds:['1']}),
 step('k','memory.identity','memory',1821,0,null,{saved:null},'SKIPPED'),
]
const ragStages=[
 step('rc','context.assemble','context',0,3,{conversationId:1041},{scope:{doc_type:'POLICY',product_id:-1}}),
 step('ri','intent_router','node',3,2,{message:rows[1].inputPreview},{intent:'AFTER_SALE_FAQ',reply_route:'agent'}),
 step('re','rag.embedding','embedding',6,91,{query:'七天无理由退货规则'},{dimensions:2560}),
 step('rd','rag.dense','retrieval',6,108,{topK:20},{error:'vector_unavailable'},'FAILED'),
 step('rb','rag.bm25','retrieval',7,36,{query:'七天无理由退货规则',topK:20},{hits:[{chunk_id:23,source:'平台退换货规则',score:8.42}]}),
 step('rf','rag.metadata_filter','retrieval',114,1,{doc_type:'POLICY',product_id:-1},{currentChunkIds:[23]}),
 step('rr','rag.rrf','retrieval',115,1,{rrfK:60,limit:10},[{chunk_id:23,source:'平台退换货规则',content:'示例规则正文：以平台当前有效售后条款为准。',bm25_score:8.42,vector_score:null,rrf_score:0.01639,matched_by:['bm25']}]),
 step('rk','rag.rerank','retrieval',116,0,null,{enabled:false,candidateCount:1},'SKIPPED'),
 step('ra','rag.answerability','retrieval',116,2,{candidateCount:1},{answerable:true,reason:'answerable',degraded_reasons:['vector_unavailable'],citations:[{id:'S1',chunk_id:23,title:'平台退换货规则'}]}),
 {...step('rm','ChatOpenAI','model',118,2900,{evidence:'[S1] 当前有效政策'}, {content:'请以商品页面与当前有效售后条款为准。[S1]'}),model:'qwen3.5:4b'},
 step('rg','output.validate','guard',3018,2,{citationRequired:true,allowedCitations:['S1']},{valid:true,citations:['S1']}),
]
rows[0].stageCount=stages.length
rows[1].stageCount=ragStages.length
request.defaults.adapter=async config=>{
 const id=config.url?.split('/').at(-1)
 let data:unknown
 if(config.url==='/admin/ai-traces/benchmark'){
   return {config,status:200,statusText:'OK',headers:{},data:{code:0,message:'success',data:{
     overallScore: 99.67, overallPassRate: 1.0, totalCases: 60,
     scorecards: [
       { category:'PRE_SALES', categoryName:'售前导购与选型', averageScore:98.0, passRate:1.0, passedCases:10, totalCases:10 },
       { category:'ORDER_FULFILLMENT', categoryName:'售中履约与订单物流', averageScore:100.0, passRate:1.0, passedCases:10, totalCases:10 },
       { category:'AFTER_SALES_POLICY', categoryName:'售后政策与三包维权', averageScore:100.0, passRate:1.0, passedCases:10, totalCases:10 },
       { category:'EMPATHY_ESCALATION', categoryName:'情绪安抚与人工接管', averageScore:100.0, passRate:1.0, passedCases:10, totalCases:10 },
       { category:'MULTI_TURN_PERSONA', categoryName:'人设约定与多轮消歧', averageScore:100.0, passRate:1.0, passedCases:10, totalCases:10 },
       { category:'SAFETY_GUARD', categoryName:'越界任务与安全红线', averageScore:100.0, passRate:1.0, passedCases:10, totalCases:10 },
     ]
   }}}
 }
 if(config.url==='/admin/ai-traces'){
   const filtered=params.has('empty')?[]:rows.filter(r=>(!config.params.status||r.status===config.params.status)&&(!config.params.conversationId||r.conversationId===config.params.conversationId)&&(!config.params.query||r.inputPreview.includes(config.params.query)))
   data={records:filtered,total:filtered.length,page:1,size:20}
 }else{
   const row=rows.find(r=>r.traceId===id)||rows[0]
   data={...row,stages:row.status==='FAILED'?[]:row.status==='DEGRADED'?ragStages:stages,omittedStages:0,error:row.status==='FAILED'?'AI 服务连接超时':null}
 }
 return {config,status:200,statusText:'OK',headers:{},data:{code:0,message:'success',data}}
}
const {default:Page}=await import('../src/views/admin/AiTraceView.vue')
const style=document.createElement('style');style.textContent='body{margin:0;background:#f5f7fa}.fixture-shell{display:grid;grid-template-columns:200px 1fr;min-height:100vh}.fixture-aside{background:white;border-right:1px solid #dde3eb;padding:25px 20px;color:#65748a;font-size:13px}.fixture-aside b{display:block;font-size:17px;color:#24466e;margin-bottom:38px}.fixture-aside p{padding:11px 0}.fixture-aside .active{color:#2563b9;font-weight:600}.fixture-content{padding:25px 28px}.fixture-warning{font-size:11px;color:#8b6b31;margin-bottom:20px}@media(max-width:700px){.fixture-shell{display:block}.fixture-aside{display:none}.fixture-content{padding:18px 12px}}';document.head.append(style)
createApp({render:()=>h('div',{class:'fixture-shell'},[
 h('aside',{class:'fixture-aside'},[h('b','AI Mall 控制台'),...['数据看板','商品管理','订单管理','知识库','用户管理','AI 链路','使用统计'].map(t=>h('p',{class:t==='AI 链路'?'active':''},t))]),
 h('main',{class:'fixture-content'},[h('div',{class:'fixture-warning'},'开发验收夹具 · 当前列表为合成测试数据，非生产执行记录'),h(Page)])
])}).mount('#app')
