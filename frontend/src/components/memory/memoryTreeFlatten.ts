import type { MemoryTreeNode } from '@/types'

export interface FlatTreeRow {
  node: MemoryTreeNode
  depth: number
}

export function flattenMemoryTree(
  roots: MemoryTreeNode[],
  expandedIds: Set<string>
): FlatTreeRow[] {
  const rows: FlatTreeRow[] = []
  const walk = (nodes: MemoryTreeNode[], depth: number) => {
    for (const node of nodes) {
      rows.push({ node, depth })
      if (node.children.length > 0 && expandedIds.has(node.id)) {
        walk(node.children, depth + 1)
      }
    }
  }
  walk(roots, 0)
  return rows
}
