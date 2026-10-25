<template>
  <div>
    <!-- 悬浮唤醒胶囊按钮（左下角） -->
    <button class="studio-launcher-btn" @click="tpl.isStudioOpen = true">
      <span class="sl-icon">🎨</span>
      <span class="sl-text">模版工坊</span>
    </button>

    <!-- 定制器抽屉 -->
    <el-drawer
      v-model="tpl.isStudioOpen"
      title="商城模版定制工坊 (Template Studio)"
      size="440px"
      direction="ltr"
      class="template-studio-drawer"
      append-to-body
    >
      <div class="studio-inner">
        <el-tabs v-model="activeTab" class="studio-tabs">
          <!-- 行业预设 -->
          <el-tab-pane label="行业模版" name="presets">
            <p class="tab-desc">一键切换不同行业的全套视觉、品牌、楼层与商品数据：</p>
            <div class="preset-cards">
              <div
                v-for="p in tpl.presets"
                :key="p.id"
                class="preset-card"
                :class="{ active: tpl.currentPresetId === p.id }"
                @click="tpl.applyPreset(p.id)"
              >
                <div class="pc-top">
                  <span class="pc-icon">{{ p.icon }}</span>
                  <span class="pc-name">{{ p.name }}</span>
                  <span v-if="tpl.currentPresetId === p.id" class="pc-tag">当前生效</span>
                </div>
                <div class="pc-brand">{{ p.brandName }} · {{ p.slogan }}</div>
                <div class="pc-colors">
                  <span class="color-swatch" :style="{ background: p.primaryColor }" />
                  <span class="color-swatch" :style="{ background: p.priceColor }" />
                  <span class="radius-info">圆角 {{ p.radius }}</span>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 楼层积木管理 -->
          <el-tab-pane label="楼层积木" name="blocks">
            <p class="tab-desc">自由增删、隐藏或上下拖拽重排首页楼层：</p>
            <div class="blocks-list">
              <div
                v-for="(sec, idx) in tpl.sections"
                :key="sec.id"
                class="block-item"
                :class="{ disabled: !sec.enabled }"
              >
                <div class="bi-left">
                  <button
                    class="eye-btn"
                    :class="{ active: sec.enabled }"
                    :title="sec.enabled ? '隐藏该楼层' : '显示该楼层'"
                    @click="tpl.toggleSection(sec.id)"
                  >
                    {{ sec.enabled ? '👁️' : '🙈' }}
                  </button>
                  <div class="bi-names">
                    <input
                      v-model="sec.title"
                      class="bi-input-title"
                      @change="tpl.updateSection(sec.id, { title: sec.title })"
                    />
                    <span class="bi-type">{{ sec.type }}</span>
                  </div>
                </div>

                <div class="bi-ops">
                  <button
                    class="op-btn"
                    :disabled="idx === 0"
                    title="上移"
                    @click="tpl.moveSection(idx, 'up')"
                  >
                    ↑
                  </button>
                  <button
                    class="op-btn"
                    :disabled="idx === tpl.sections.length - 1"
                    title="下移"
                    @click="tpl.moveSection(idx, 'down')"
                  >
                    ↓
                  </button>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 品牌与样式 -->
          <el-tab-pane label="品牌与外观" name="styles">
            <div class="form-group">
              <label class="form-label">商城名称</label>
              <el-input v-model="tpl.brand.name" @change="saveConfig" />
            </div>

            <div class="form-group">
              <label class="form-label">品牌 Slogan</label>
              <el-input v-model="tpl.brand.slogan" @change="saveConfig" />
            </div>

            <div class="form-group">
              <label class="form-label">Logo 徽标文字</label>
              <el-input v-model="tpl.brand.logoBadge" @change="saveConfig" />
            </div>

            <div class="form-group">
              <label class="form-label">品牌主色调</label>
              <div class="color-picker-row">
                <input
                  v-model="tpl.theme.primaryColor"
                  type="color"
                  class="native-color"
                  @change="updateThemeVars"
                />
                <span class="color-hex">{{ tpl.theme.primaryColor }}</span>
                <div class="color-quick-row">
                  <span
                    v-for="c in QUICK_COLORS"
                    :key="c"
                    class="quick-dot"
                    :style="{ background: c }"
                    @click="setPrimaryColor(c)"
                  />
                </div>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">卡片微圆角</label>
              <el-radio-group v-model="tpl.theme.radius" size="small" @change="updateThemeVars">
                <el-radio-button label="0px">直角</el-radio-button>
                <el-radio-button label="6px">极简微圆</el-radio-button>
                <el-radio-button label="10px">标准现代</el-radio-button>
                <el-radio-button label="16px">大圆角</el-radio-button>
              </el-radio-group>
            </div>
          </el-tab-pane>

          <!-- 配置导出与导入 -->
          <el-tab-pane label="导出/导入" name="io">
            <p class="tab-desc">当前全套模版架构配置（JSON 格式）：</p>
            <textarea :value="tpl.exportConfigJson()" class="json-textarea" readonly />

            <div class="io-actions">
              <el-button type="primary" size="small" @click="copyJson">
                复制配置 JSON
              </el-button>
              <el-button size="small" @click="tpl.resetDefault">
                恢复默认预设
              </el-button>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useTemplateStore } from '@/stores/template'

const tpl = useTemplateStore()
const activeTab = ref('presets')

const QUICK_COLORS = ['#2563eb', '#18181b', '#059669', '#e11d48', '#ea580c', '#7c3aed']

function setPrimaryColor(c: string) {
  tpl.theme.primaryColor = c
  updateThemeVars()
}

function updateThemeVars() {
  tpl.applyCssVars()
}

function saveConfig() {
  tpl.applyCssVars()
}

function copyJson() {
  navigator.clipboard.writeText(tpl.exportConfigJson())
  ElMessage.success('配置已成功复制到剪贴板，可直接作为新模版保存！')
}
</script>

<style scoped>
.studio-launcher-btn {
  position: fixed;
  left: 20px;
  bottom: 84px;
  display: flex;
  align-items: center;
  gap: 6px;
  background: #18181b;
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 8px 16px;
  border-radius: 9999px;
  box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.35);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  z-index: 85;
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease;
}

html.dark .studio-launcher-btn {
  background: #ffffff;
  color: #18181b;
}

.studio-launcher-btn:hover {
  transform: translateY(-2px) scale(1.04);
}

.sl-icon {
  font-size: 16px;
}

.studio-inner {
  padding: 4px 6px;
}

.tab-desc {
  font-size: 12px;
  color: #71717a;
  margin: 0 0 14px;
  line-height: 1.5;
}

/* 预设卡片 */
.preset-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preset-card {
  border: 1.5px solid var(--mall-border, #e4e4e7);
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--mall-surface, #ffffff);
}

.preset-card:hover {
  border-color: #18181b;
}

.preset-card.active {
  border-color: var(--el-color-primary, #2563eb);
  background: rgba(37, 99, 235, 0.04);
}

.pc-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.pc-icon {
  font-size: 20px;
}

.pc-name {
  font-size: 14px;
  font-weight: 700;
  color: #18181b;
}

html.dark .pc-name {
  color: #f4f4f5;
}

.pc-tag {
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: var(--el-color-primary, #2563eb);
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: auto;
}

.pc-brand {
  font-size: 12px;
  color: #71717a;
  margin-bottom: 10px;
}

.pc-colors {
  display: flex;
  align-items: center;
  gap: 6px;
}

.color-swatch {
  width: 16px;
  height: 16px;
  border-radius: 9999px;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.radius-info {
  font-size: 11px;
  color: #a1a1aa;
  margin-left: auto;
}

/* 积木楼层 */
.blocks-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.block-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid var(--mall-border, #e4e4e7);
  border-radius: 8px;
  padding: 8px 12px;
  background: var(--mall-surface, #ffffff);
  transition: opacity 0.2s ease;
}

.block-item.disabled {
  opacity: 0.45;
  background: var(--mall-surface-2, #f4f4f5);
}

.bi-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.eye-btn {
  border: none;
  background: transparent;
  font-size: 16px;
  cursor: pointer;
  padding: 2px;
}

.bi-names {
  display: flex;
  flex-direction: column;
}

.bi-input-title {
  border: 1px solid transparent;
  background: transparent;
  font-size: 13px;
  font-weight: 600;
  color: #18181b;
  outline: none;
  padding: 2px 4px;
  border-radius: 4px;
}

html.dark .bi-input-title {
  color: #f4f4f5;
}

.bi-input-title:focus {
  border-color: #2563eb;
  background: var(--mall-surface, #ffffff);
}

.bi-type {
  font-size: 10px;
  color: #a1a1aa;
  padding-left: 4px;
}

.bi-ops {
  display: flex;
  gap: 4px;
}

.op-btn {
  width: 26px;
  height: 26px;
  border: 1px solid var(--mall-border, #e4e4e7);
  background: var(--mall-surface-2, #f4f4f5);
  border-radius: 4px;
  cursor: pointer;
  font-weight: 700;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.op-btn:disabled {
  opacity: 0.25;
  cursor: not-allowed;
}

/* 品牌与外观 */
.form-group {
  margin-bottom: 18px;
}

.form-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #71717a;
  margin-bottom: 6px;
}

.color-picker-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.native-color {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.color-hex {
  font-size: 12px;
  font-family: monospace;
  color: #71717a;
}

.color-quick-row {
  display: flex;
  gap: 6px;
  margin-left: auto;
}

.quick-dot {
  width: 20px;
  height: 20px;
  border-radius: 9999px;
  cursor: pointer;
  border: 1px solid rgba(0, 0, 0, 0.1);
  transition: transform 0.15s ease;
}

.quick-dot:hover {
  transform: scale(1.15);
}

/* JSON 文本区 */
.json-textarea {
  width: 100%;
  height: 240px;
  border: 1px solid var(--mall-border, #e4e4e7);
  border-radius: 8px;
  padding: 10px;
  font-family: monospace;
  font-size: 11px;
  color: #3f3f46;
  background: var(--mall-surface-2, #f4f4f5);
  resize: none;
  outline: none;
}

html.dark .json-textarea {
  color: #a1a1aa;
  background: #18181b;
}

.io-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

@media (max-width: 768px) {
  .studio-launcher-btn {
    left: 14px;
    bottom: calc(64px + env(safe-area-inset-bottom));
    padding: 6px 12px;
    font-size: 12px;
  }
}
</style>
