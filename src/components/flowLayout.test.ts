import { describe, expect, it } from 'vitest'
import { layoutNodes, wouldCreateCycle, type FlowNodeLike } from './flowLayout'

describe('wouldCreateCycle', () => {
  const nodes: FlowNodeLike[] = [
    { nodeKey: 'a', dependsOn: [] },
    { nodeKey: 'b', dependsOn: ['a'] },
    { nodeKey: 'c', dependsOn: ['b'] },
    { nodeKey: 'd', dependsOn: ['a', 'c'] },
  ]

  it('拒绝自依赖', () => {
    expect(wouldCreateCycle(nodes, 'a', 'a')).toBe(true)
  })

  it('允许新增无环依赖', () => {
    expect(wouldCreateCycle(nodes, 'd', 'a')).toBe(false)
    expect(wouldCreateCycle(nodes, 'c', 'b')).toBe(false)
  })

  it('拒绝形成环的依赖（目标节点沿依赖链能回到起点）', () => {
    expect(wouldCreateCycle(nodes, 'c', 'd')).toBe(true) // d 已依赖 c，再加 c→d 会闭环
    expect(wouldCreateCycle(nodes, 'b', 'd')).toBe(true) // b→c→d→b
  })

  it('依赖节点不存在时允许（由上层过滤）', () => {
    expect(wouldCreateCycle(nodes, 'ghost', 'b')).toBe(false)
  })
})

describe('layoutNodes', () => {
  it('按依赖深度分列排布并写入 config.canvas', () => {
    const nodes: FlowNodeLike[] = [
      { nodeKey: 'plan', dependsOn: [], config: {} },
      { nodeKey: 'extract', dependsOn: ['plan'], config: {} },
      { nodeKey: 'review', dependsOn: ['extract'], config: {} },
      { nodeKey: 'audit', dependsOn: ['plan'], config: {} },
    ]
    layoutNodes(nodes, { xSpacing: 190, ySpacing: 100, x0: 36, y0: 210 })
    const pos = Object.fromEntries(nodes.map(n => [n.nodeKey, n.config!.canvas]))
    // 深度列：plan 在最左，extract/audit 次之，review 最右
    expect(pos.plan.x).toBeLessThan(pos.extract.x)
    expect(pos.extract.x).toBe(pos.audit.x)
    expect(pos.extract.x).toBeLessThan(pos.review.x)
    // 同列节点垂直分布
    expect(pos.extract.y).not.toBe(pos.audit.y)
    // 同列以 y0 为中心对称
    expect((pos.extract.y + pos.audit.y) / 2).toBeCloseTo(210, 5)
    // 保留已有 config 字段
    const preserved: FlowNodeLike = { nodeKey: 'x', dependsOn: [], config: { tag: 'keep' } }
    layoutNodes([preserved])
    expect(preserved.config!.tag).toBe('keep')
    expect(preserved.config!.canvas).toBeDefined()
  })

  it('空依赖列表不报错', () => {
    expect(() => layoutNodes([])).not.toThrow()
  })
})
