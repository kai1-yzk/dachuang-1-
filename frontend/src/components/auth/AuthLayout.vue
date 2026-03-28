<template>
  <div class="auth-root">
    <div class="auth-overlay" />
    <div class="auth-grid-lines" />

    <div class="auth-shell">
      <div class="auth-grid">
        <section class="auth-visual" aria-hidden="true">
          <div class="brand">
            <div class="brand-mark">AIOps</div>
            <div class="brand-sub">企业级智能运维与安全工作台</div>
          </div>

          <div class="visual-copy">
            <div class="visual-badge">OBSERVE · DEFEND · EXECUTE</div>
            <div class="visual-title">{{ visualTitle }}</div>
            <div class="visual-subtitle">{{ visualSubtitle }}</div>
          </div>

          <div class="visual-panels">
            <div class="visual-panel">
              <div class="visual-panel__label">实时监控</div>
              <div class="visual-panel__value">24/7</div>
              <div class="visual-panel__meta">持续观测关键资源与业务波动</div>
            </div>
            <div class="visual-panel">
              <div class="visual-panel__label">风险处置</div>
              <div class="visual-panel__value">AI + Rule</div>
              <div class="visual-panel__meta">将安全拦截、执行审批与审计归档串联起来</div>
            </div>
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
const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  visualTitle: { type: String, default: '守护你的关键服务' },
  visualSubtitle: { type: String, default: '更快发现风险、更稳保障可用性。' }
})
</script>

<style scoped>
.auth-root {
  min-height: 100vh;
  width: 100%;
  position: relative;
  background:
    radial-gradient(circle at 15% 20%, rgba(14, 165, 233, 0.25), transparent 24%),
    radial-gradient(circle at 78% 18%, rgba(37, 99, 235, 0.28), transparent 22%),
    linear-gradient(135deg, #06111f 0%, #0f172a 42%, #111c36 100%);
  overflow: hidden;
}

.auth-overlay {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(6, 17, 31, 0.45) 0%, rgba(6, 17, 31, 0.56) 45%, rgba(6, 17, 31, 0.78) 100%),
    radial-gradient(900px 520px at 15% 18%, rgba(56, 189, 248, 0.18), transparent 60%),
    radial-gradient(900px 520px at 70% 15%, rgba(59, 130, 246, 0.18), transparent 60%);
}

.auth-grid-lines {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px);
  background-size: 54px 54px;
  mask-image: radial-gradient(circle at center, black 40%, transparent 90%);
  opacity: 0.35;
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
  align-items: center;
}

.auth-visual {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 30px;
  padding: 20px 16px;
}

.brand {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.brand-mark {
  width: fit-content;
  padding: 10px 14px;
  border-radius: 999px;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #e0f2fe;
  background: rgba(56, 189, 248, 0.14);
  border: 1px solid rgba(125, 211, 252, 0.16);
}

.brand-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.75);
}

.visual-copy {
  max-width: 520px;
}

.visual-badge {
  display: inline-flex;
  margin-bottom: 18px;
  padding: 8px 12px;
  border-radius: 999px;
  color: #bfdbfe;
  background: rgba(37, 99, 235, 0.18);
  border: 1px solid rgba(96, 165, 250, 0.18);
  font-size: 12px;
  letter-spacing: 0.08em;
}

.visual-title {
  font-size: clamp(34px, 4vw, 54px);
  line-height: 1.06;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.92);
  letter-spacing: 0.2px;
}

.visual-subtitle {
  margin-top: 16px;
  font-size: 15px;
  line-height: 1.9;
  color: rgba(255, 255, 255, 0.72);
}

.visual-panels {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  max-width: 640px;
}

.visual-panel {
  padding: 18px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(16px);
}

.visual-panel__label {
  font-size: 12px;
  color: rgba(191, 219, 254, 0.72);
}

.visual-panel__value {
  margin-top: 10px;
  font-size: 24px;
  font-weight: 800;
  color: #f8fafc;
}

.visual-panel__meta {
  margin-top: 8px;
  color: rgba(226, 232, 240, 0.7);
  font-size: 13px;
  line-height: 1.6;
}

.auth-panel {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 16px;
}

.auth-card {
  width: min(420px, 100%);
  border-radius: 28px;
  box-shadow: 0 28px 70px rgba(2, 8, 23, 0.35);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.58);
  padding: 28px;
  box-sizing: border-box;
}

.auth-card-header {
  margin-bottom: 14px;
}

.auth-title {
  margin: 0;
  font-size: 28px;
  line-height: 1.25;
  font-weight: 800;
  color: #0f172a;
}

.auth-subtitle {
  margin: 8px 0 0 0;
  font-size: 14px;
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
    border-radius: 24px;
    background: rgba(11, 18, 32, 0.32);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .visual-panels {
    grid-template-columns: 1fr;
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
