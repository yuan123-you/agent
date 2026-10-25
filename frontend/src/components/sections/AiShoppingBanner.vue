<template>
  <section class="ai-banner-section container">
    <div class="ai-card" @click="$router.push('/assistant')">
      <div class="ai-left">
        <div class="ai-pill">
          <span class="sparkle">✨</span>
          <span>AI 智能导购引擎 · 24H 即时服务</span>
        </div>
        <h3 class="ai-heading">不知道买什么？问问 AI 专属购物顾问</h3>
        <p class="ai-sub">
          深度解析商品参数、跨品类智能比价、7天价保咨询，一键开启自然语言导购新体验。
        </p>
        <div class="ai-prompts">
          <span class="prompt-chip" @click.stop="askAi('推荐 3000 元内性价比最高的轻薄笔记本')">
            💬 "推荐 3000 元内轻薄笔记本"
          </span>
          <span class="prompt-chip" @click.stop="askAi('有哪些适合送礼的数码好物？')">
            💬 "送礼数码好物精选"
          </span>
          <span class="prompt-chip" @click.stop="askAi('当前有哪些全场满减优惠券可领？')">
            💬 "查询当前可用优惠券"
          </span>
        </div>
      </div>
      <div class="ai-right">
        <button class="ai-cta-btn">
          <span>进入 AI 助手</span>
          <el-icon><ArrowRight /></el-icon>
        </button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'

const router = useRouter()

function askAi(promptText: string) {
  router.push({ path: '/assistant', query: { prompt: promptText } })
}
</script>

<style scoped>
.ai-banner-section {
  margin: 32px auto;
}

.ai-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  background: radial-gradient(ellipse at 90% 50%, rgba(37, 99, 235, 0.12), transparent 60%),
              linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(37, 99, 235, 0.2);
  border-radius: var(--mall-radius-lg, 14px);
  padding: 28px 36px;
  cursor: pointer;
  box-shadow: 0 4px 20px -2px rgba(37, 99, 235, 0.08);
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

html.dark .ai-card {
  background: radial-gradient(ellipse at 90% 50%, rgba(59, 130, 246, 0.2), transparent 60%),
              linear-gradient(135deg, #131722 0%, #0c0f17 100%);
  border-color: rgba(59, 130, 246, 0.25);
  box-shadow: 0 4px 24px -2px rgba(0, 0, 0, 0.5);
}

.ai-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 30px -4px rgba(37, 99, 235, 0.16);
}

.ai-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.08);
  padding: 4px 12px;
  border-radius: 9999px;
  margin-bottom: 12px;
}

html.dark .ai-pill {
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.15);
}

.ai-heading {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 8px;
  letter-spacing: -0.02em;
}

html.dark .ai-heading {
  color: #f8fafc;
}

.ai-sub {
  font-size: 14px;
  color: #64748b;
  margin: 0 0 16px;
  line-height: 1.5;
  max-width: 620px;
}

html.dark .ai-sub {
  color: #94a3b8;
}

.ai-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.prompt-chip {
  font-size: 12px;
  color: #334155;
  background: var(--mall-surface, #ffffff);
  border: 1px solid var(--mall-border, #e2e8f0);
  border-radius: 6px;
  padding: 4px 10px;
  transition: all 0.18s ease;
}

html.dark .prompt-chip {
  color: #cbd5e1;
  background: #1e293b;
  border-color: #334155;
}

.prompt-chip:hover {
  border-color: #2563eb;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.04);
}

.ai-cta-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--el-color-primary, #2563eb);
  color: #ffffff;
  border: none;
  font-size: 14px;
  font-weight: 600;
  padding: 12px 24px;
  border-radius: 9999px;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
  transition: all 0.2s ease;
}

.ai-cta-btn:hover {
  background: #1d4ed8;
  transform: scale(1.03);
}

@media (max-width: 768px) {
  .ai-card {
    flex-direction: column;
    align-items: flex-start;
    padding: 20px;
  }
  .ai-heading {
    font-size: 18px;
  }
  .ai-sub {
    font-size: 13px;
  }
  .ai-right {
    width: 100%;
  }
  .ai-cta-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
