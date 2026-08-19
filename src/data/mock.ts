import type { Iteration, Project, Task } from '../types'

export const projects: Project[] = [
  {
    id: 'leave-hub', name: '员工假勤管理平台',
    description: '覆盖请假申请、多级审批、额度管理与数据分析的一体化内部应用。',
    status: 'executing', progress: 72, version: 'v1.3.0', template: 'Web 全栈应用', owner: '林嘉',
    updatedAt: '10 分钟前', members: ['LJ', 'ZW', 'CY', 'YH'], tasks: { done: 18, total: 25 }, risk: 'low',
  },
  {
    id: 'supplier-risk', name: '供应商风险评估系统',
    description: '汇聚供应商履约、财务与舆情数据，生成分级风险画像和预警。',
    status: 'testing', progress: 86, version: 'v1.0.0-rc.2', template: 'Web 全栈应用', owner: '赵玮',
    updatedAt: '1 小时前', members: ['ZW', 'WL', 'YH'], tasks: { done: 31, total: 36 }, risk: 'medium',
  },
  {
    id: 'contract-api', name: '合同审查 API 服务',
    description: '提供合同条款抽取、风险识别和审查意见生成的标准化 API。',
    status: 'completed', progress: 100, version: 'v2.1.0', template: 'API 后端服务', owner: '陈屿',
    updatedAt: '昨天 16:42', members: ['CY', 'ZW'], tasks: { done: 22, total: 22 }, risk: 'low',
  },
  {
    id: 'ops-board', name: '运营数据驾驶舱',
    description: '面向区域运营团队的核心指标监控、趋势分析与异常下钻看板。',
    status: 'draft', progress: 12, version: '—', template: '前端应用', owner: '林嘉',
    updatedAt: '3 天前', members: ['LJ'], tasks: { done: 2, total: 17 }, risk: 'low',
  },
]

export const tasks: Task[] = [
  { id: 't-root', parentId: null, name: '项目规划与执行协调', agent: '项目经理智能体', agentShort: 'PM', status: 'in_progress', progress: 72, duration: '2h 48m', startedAt: '今天 09:31', description: '统筹本次增量迭代，持续评估任务依赖和项目风险。', tokens: '28.4k' },
  { id: 't-req', parentId: 't-root', name: '需求解析与影响分析', agent: '需求分析智能体', agentShort: 'RA', status: 'completed', progress: 100, duration: '12m', startedAt: '今天 09:32', incremental: true, description: '结合当前代码、API 和历史需求，识别本次导出功能的影响范围。', files: 0, tokens: '8.2k' },
  { id: 't-arch', parentId: 't-root', name: '增量技术方案设计', agent: '架构设计智能体', agentShort: 'AR', status: 'completed', progress: 100, duration: '18m', startedAt: '今天 09:45', incremental: true, description: '设计不破坏既有接口的导出任务与文件存储方案。', files: 2, tokens: '12.7k' },
  { id: 't-back', parentId: 't-arch', name: '开发报表导出接口', agent: '后端开发智能体', agentShort: 'BE', status: 'completed', progress: 100, duration: '48m', startedAt: '今天 10:06', incremental: true, description: '实现按筛选条件导出 Excel 的异步任务接口及权限校验。', files: 7, tokens: '24.1k' },
  { id: 't-front', parentId: 't-arch', name: '新增导出交互组件', agent: '前端开发智能体', agentShort: 'FE', status: 'completed', progress: 100, duration: '36m', startedAt: '今天 10:07', incremental: true, description: '在假勤报表页增加导出入口、进度反馈和下载状态。', files: 5, tokens: '18.9k' },
  { id: 't-review', parentId: 't-root', name: '增量代码审查', agent: '代码审查智能体', agentShort: 'CR', status: 'completed', progress: 100, duration: '21m', startedAt: '今天 10:58', incremental: true, description: '检查兼容性、安全性、重复实现以及数据库访问性能。', files: 12, tokens: '13.5k' },
  { id: 't-test', parentId: 't-root', name: '回归测试与质量验证', agent: '测试工程师智能体', agentShort: 'QA', status: 'in_progress', progress: 68, duration: '31m', startedAt: '今天 11:22', incremental: true, description: '执行 128 项既有回归用例和 24 项新增导出功能测试，验证已有功能不受影响。', files: 8, tokens: '16.3k' },
  { id: 't-deploy', parentId: 't-root', name: '构建镜像并灰度部署', agent: '部署智能体', agentShort: 'DO', status: 'pending', progress: 0, duration: '—', startedAt: '待测试通过', incremental: true, description: '构建 v1.3.0 镜像，完成灰度部署与冒烟测试。', files: 0, tokens: '—' },
]

export const iterations: Iteration[] = [
  { id: 'i-130', version: 'v1.3.0', title: '新增报表 Excel 导出', description: '支持按部门、日期和审批状态筛选后导出假勤明细，增加异步进度反馈。', date: '2026-08-17 09:31', author: '林嘉', status: 'executing', files: 12, added: 684, removed: 57, tests: 92, deployStatus: '等待回归测试', type: 'feature' },
  { id: 'i-120', version: 'v1.2.0', title: '审批流程支持三级配置', description: '审批节点由固定两级升级为可配置三级，兼容历史审批单据。', date: '2026-08-12 16:42', author: '赵玮', status: 'completed', files: 18, added: 1126, removed: 241, tests: 100, deployStatus: '运行中', type: 'feature' },
  { id: 'i-111', version: 'v1.1.1', title: '修复跨月额度计算问题', description: '修复跨月请假申请在额度扣减时的边界计算错误。', date: '2026-08-07 11:16', author: '陈屿', status: 'completed', files: 4, added: 73, removed: 31, tests: 100, deployStatus: '已归档', type: 'fix' },
  { id: 'i-110', version: 'v1.1.0', title: '新增团队假勤日历', description: '新增团队维度的月历视图，支持权限范围内的人员筛选。', date: '2026-08-01 18:05', author: '林嘉', status: 'completed', files: 14, added: 897, removed: 102, tests: 98, deployStatus: '已归档', type: 'feature' },
  { id: 'i-100', version: 'v1.0.0', title: '首个生产版本', description: '完成请假申请、两级审批、额度管理和基础数据报表。', date: '2026-07-29 15:30', author: '林嘉', status: 'completed', files: 86, added: 7642, removed: 0, tests: 96, deployStatus: '已归档', type: 'initial' },
]

export const taskLogs = [
  { time: '11:22:08.014', type: 'system', text: '测试工程师智能体已启动，加载迭代 i-130 上下文。' },
  { time: '11:22:10.327', type: 'info', text: '读取变更影响分析：后端 7 个文件，前端 5 个文件，数据库 Schema 无变更。' },
  { time: '11:22:14.881', type: 'tool', text: 'tool.read_file → tests/regression/test_leave_approval.py' },
  { time: '11:22:15.293', type: 'success', text: '已识别 128 项既有回归用例，准备增量生成针对性用例。' },
  { time: '11:23:02.102', type: 'tool', text: 'tool.write_file → tests/export/test_report_export.py  (+186 lines)' },
  { time: '11:23:05.640', type: 'thinking', text: '正在覆盖权限边界、空数据集、超大数据量和多语言文件名场景…' },
  { time: '11:24:31.098', type: 'tool', text: 'tool.shell → pytest tests/regression tests/export -q --maxfail=1' },
  { time: '11:37:45.517', type: 'success', text: '第一批 104/104 项测试通过，用时 13m 14s。' },
  { time: '11:38:01.225', type: 'info', text: '正在执行 E2E：用户筛选假勤记录 → 发起导出 → 查询进度 → 下载文件。' },
  { time: '11:51:19.071', type: 'warning', text: '发现文件名时区断言不稳定，已隔离并重新执行该用例。' },
  { time: '11:53:42.812', type: 'success', text: '重试通过。当前进度 68%，已通过 104 / 152。' },
]
