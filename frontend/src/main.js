import { createApp } from 'vue'
import App from './App.vue'
import './styles/theme.css'
import router from './router'
import { createPinia } from 'pinia'

// Element Plus 按需引入
//
// 全量 `app.use(ElementPlus)` 会把所有组件打进一个 900KB+ 的 chunk。
// 这里改为只注册项目实际用到的组件，并按需引入各自的样式文件。
// 新增组件时，需在此处补注册并补对应样式 import。
import {
  ElAlert,
  ElAvatar,
  ElButton,
  ElCard,
  ElCheckbox,
  ElCol,
  ElDatePicker,
  ElDescriptions,
  ElDescriptionsItem,
  ElDialog,
  ElDivider,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElLink,
  ElOption,
  ElPagination,
  ElProgress,
  ElRadio,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElSpace,
  ElStep,
  ElSteps,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTimeline,
  ElTimelineItem,
} from 'element-plus'

import 'element-plus/theme-chalk/base.css'
import 'element-plus/theme-chalk/el-alert.css'
import 'element-plus/theme-chalk/el-avatar.css'
import 'element-plus/theme-chalk/el-button.css'
import 'element-plus/theme-chalk/el-card.css'
import 'element-plus/theme-chalk/el-checkbox.css'
import 'element-plus/theme-chalk/el-col.css'
import 'element-plus/theme-chalk/el-date-picker.css'
import 'element-plus/theme-chalk/el-descriptions.css'
import 'element-plus/theme-chalk/el-dialog.css'
import 'element-plus/theme-chalk/el-divider.css'
import 'element-plus/theme-chalk/el-dropdown.css'
import 'element-plus/theme-chalk/el-empty.css'
import 'element-plus/theme-chalk/el-form.css'
import 'element-plus/theme-chalk/el-icon.css'
import 'element-plus/theme-chalk/el-input.css'
import 'element-plus/theme-chalk/el-input-number.css'
import 'element-plus/theme-chalk/el-link.css'
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-option.css'
import 'element-plus/theme-chalk/el-pagination.css'
import 'element-plus/theme-chalk/el-progress.css'
import 'element-plus/theme-chalk/el-radio.css'
import 'element-plus/theme-chalk/el-row.css'
import 'element-plus/theme-chalk/el-select.css'
import 'element-plus/theme-chalk/el-space.css'
import 'element-plus/theme-chalk/el-step.css'
import 'element-plus/theme-chalk/el-switch.css'
import 'element-plus/theme-chalk/el-table.css'
import 'element-plus/theme-chalk/el-tag.css'
import 'element-plus/theme-chalk/el-timeline.css'

const components = [
  ElAlert,
  ElAvatar,
  ElButton,
  ElCard,
  ElCheckbox,
  ElCol,
  ElDatePicker,
  ElDescriptions,
  ElDescriptionsItem,
  ElDialog,
  ElDivider,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElLink,
  ElOption,
  ElPagination,
  ElProgress,
  ElRadio,
  ElRadioGroup,
  ElRow,
  ElSelect,
  ElSpace,
  ElStep,
  ElSteps,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTimeline,
  ElTimelineItem,
]

const app = createApp(App)

for (const component of components) {
  app.component(component.name, component)
}

// 图标按需注册：全量注册 @element-plus/icons-vue 会额外打包上百个图标。
// App.vue 的菜单通过 `icon: 'Platform'` 这类动态组件名引用，故仍需全局注册。
import { ArrowDown, Platform, Position } from '@element-plus/icons-vue'

app.component('ArrowDown', ArrowDown)
app.component('Platform', Platform)
app.component('Position', Position)

app.use(createPinia())
app.use(router)

app.mount('#app')
