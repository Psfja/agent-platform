// 流程图布局与依赖校验的纯函数（便于单元测试）
export interface FlowNodeLike {
  nodeKey: string
  dependsOn: string[]
  config?: Record<string, any>
}

/** 判断新增 from → to 依赖是否会形成环（to 沿依赖链向上能否回到 from） */
export function wouldCreateCycle(nodes: FlowNodeLike[], from: string, to: string): boolean {
  if (from === to) return true
  const stack = [to]
  const visited = new Set<string>()
  while (stack.length) {
    const current = stack.pop()!
    if (current === from) return true
    if (visited.has(current)) continue
    visited.add(current)
    const node = nodes.find(n => n.nodeKey === current)
    if (node) stack.push(...node.dependsOn)
  }
  return false
}

/** 按依赖深度计算每个节点的画布坐标，写入 node.config.canvas（x 为深度列，y 按同列居中分布） */
export function layoutNodes(nodes: FlowNodeLike[], opts: { xSpacing?: number; ySpacing?: number; x0?: number; y0?: number } = {}): void {
  const { xSpacing = 190, ySpacing = 100, x0 = 36, y0 = 210 } = opts
  const depthOf = (key: string, seen: string[] = []): number => {
    if (seen.includes(key)) return 0
    const node = nodes.find(n => n.nodeKey === key)
    if (!node) return 0
    return 1 + Math.max(0, ...node.dependsOn.map(d => depthOf(d, [...seen, key])))
  }
  const withDepth = nodes.map(node => ({ node, depth: depthOf(node.nodeKey) }))
  const totalByDepth = new Map<number, number>()
  for (const { depth } of withDepth) totalByDepth.set(depth, (totalByDepth.get(depth) || 0) + 1)
  const slotByDepth = new Map<number, number>()
  for (const { node, depth } of withDepth) {
    const slot = slotByDepth.get(depth) || 0
    slotByDepth.set(depth, slot + 1)
    const total = totalByDepth.get(depth) || 1
    const x = x0 + (depth - 1) * xSpacing
    const y = y0 + (slot - (total - 1) / 2) * ySpacing
    node.config = { ...(node.config || {}), canvas: { x, y } }
  }
}
