<template>
  <div class="auth-root" :style="rootStyle">
    <div class="auth-overlay" />

    <div class="auth-shell">
      <div class="auth-grid">
        <section class="auth-visual" aria-hidden="true">
          <div class="brand">
            <div class="brand-mark">AI Ops Sec</div>
            <div class="brand-sub">轻量化 AI 服务器运维防护系统</div>
          </div>

          <div class="visual-copy">
            <div class="visual-title">{{ visualTitle }}</div>
            <div class="visual-subtitle">{{ visualSubtitle }}</div>
          </div>
        </section>

        <section class="auth-panel">
          <div class="auth-card">
            <header class="auth-card-header">
              <h1 class="auth-title">{{ title }}</h1>
              <p v-if="subtitle" class="auth-subtitle">{{ subtitle }}</p>
            </header>

            <div class="auth-card-body">
              <slot />
            </div>

            <div v-if="$slots.footer" class="auth-card-footer">
              <slot name="footer" />
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const defaultImagePrompt = encodeURIComponent(
  'modern cybersecurity operations center, abstract technology background, dark navy gradient, subtle grid texture, glowing blue and teal accents, cinematic lighting, minimal, no text, ultra wide, high detail'
)

const defaultImageUrl = `https://coresg-normal.trae.ai/api/ide/v1/text_to_image?prompt=${defaultImagePrompt}&image_size=landscape_16_9`

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  imageUrl: { type: String, default: '' },
  visualTitle: { type: String, default: '守护你的关键服务' },
  visualSubtitle: { type: String, default: '更快发现风险、更稳保障可用性。' }
})

const rootStyle = computed(() => {
  const url = props.imageUrl || defaultImageUrl
  return {
    backgroundImage: `url("${url}")`
  }
})
</script>

<style scoped>
.auth-root {
  min-height: 100vh;
  width: 100%;
  position: relative;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  background-color: #0b1220;
}

.auth-overlay {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(11, 18, 32, 0.55) 0%, rgba(11, 18, 32, 0.65) 45%, rgba(11, 18, 32, 0.78) 72%, rgba(11, 18, 32, 0.88) 100%),
    radial-gradient(1200px 600px at 20% 20%, rgba(64, 158, 255, 0.18), transparent 55%),
    radial-gradient(1000px 520px at 65% 35%, rgba(54, 207, 201, 0.14), transparent 60%);
}

.auth-shell {
  position: relative;
  min-height: 100vh;
  width: 100%;
  display: flex;
  align-items: stretch;
  justify-content: center;
}

.auth-grid {
  width: min(1200px, 100%);
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 24px;
  padding: 32px;
  box-sizing: border-box;
}

.auth-visual {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 20px 16px;
}

.brand {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.brand-mark {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.2px;
  background: linear-gradient(90deg, #409eff, #36cfc9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.brand-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.75);
}

.visual-copy {
  max-width: 520px;
}

.visual-title {
  font-size: 34px;
  line-height: 1.2;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.92);
  letter-spacing: 0.2px;
}

.visual-subtitle {
  margin-top: 10px;
  font-size: 14px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.72);
}

.auth-panel {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 16px;
}

.auth-card {
  width: min(420px, 100%);
  border-radius: 12px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.25);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  padding: 22px;
  box-sizing: border-box;
}

.auth-card-header {
  margin-bottom: 14px;
}

.auth-title {
  margin: 0;
  font-size: 22px;
  line-height: 1.25;
  font-weight: 700;
  color: #0f172a;
}

.auth-subtitle {
  margin: 8px 0 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
}

.auth-card-body {
  width: 100%;
}

.auth-card-footer {
  margin-top: 14px;
}

@media (max-width: 1024px) {
  .auth-grid {
    grid-template-columns: 1fr;
    padding: 18px;
    gap: 14px;
  }

  .auth-visual {
    min-height: 200px;
    padding: 16px;
    border-radius: 14px;
    background: rgba(11, 18, 32, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .visual-title {
    font-size: 26px;
  }

  .auth-panel {
    justify-content: center;
    padding-right: 0;
    padding-bottom: 18px;
  }
}

@media (max-width: 420px) {
  .auth-card {
    padding: 18px;
  }
}
</style>
