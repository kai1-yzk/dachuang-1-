// ECharts 按需引入
//
// 全量 `import * as echarts from 'echarts'` 会把所有图表类型与组件打进主包，
// 单个 chunk 超过 1MB。这里只注册本项目实际用到的部分（折线图 + 基础组件），
// 显著减小产物体积。新增图表类型时，在此处补充对应的 use() 注册。
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DatasetComponent,
  TransformComponent,
} from 'echarts/components'
import { LabelLayout, UniversalTransition } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DatasetComponent,
  TransformComponent,
  LabelLayout,
  UniversalTransition,
  CanvasRenderer,
])

export default echarts
