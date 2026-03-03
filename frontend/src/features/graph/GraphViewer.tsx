import { useRef, useEffect, useCallback, useMemo } from "react";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d";
import type { GraphNode, GraphEdge } from "@/api/types";

// Color mapping for entity types
const TYPE_COLORS: Record<string, string> = {
  person: "#3b82f6",
  organization: "#10b981",
  place: "#f59e0b",
  concept: "#8b5cf6",
  technology: "#06b6d4",
  event: "#ef4444",
  theory: "#ec4899",
  Book: "#f97316",
  Author: "#6366f1",
  Chapter: "#64748b",
  Topic: "#14b8a6",
  Entity: "#a855f7",
};

interface GraphViewerNode {
  id: string;
  name: string;
  type: string;
  label: string;
  connections_count: number;
  val: number;
  color: string;
  x?: number;
  y?: number;
}

interface GraphViewerLink {
  source: string;
  target: string;
  relationship: string;
}

interface GraphViewerProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  centerId?: string;
  width?: number;
  height?: number;
  onNodeClick?: (nodeId: string) => void;
}

export function GraphViewer({
  nodes,
  edges,
  centerId,
  width = 800,
  height = 600,
  onNodeClick,
}: GraphViewerProps) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<ForceGraphMethods<any, any>>(undefined);

  const graphData = useMemo(() => {
    const nodeMap = new Set(nodes.map((n) => n.id));

    const graphNodes: GraphViewerNode[] = nodes.map((n) => ({
      id: n.id,
      name: n.name,
      type: n.type || n.label,
      label: n.label,
      connections_count: n.connections_count,
      val: Math.max(2, Math.min(10, (n.connections_count || 1) * 1.5)),
      color: TYPE_COLORS[n.type] || TYPE_COLORS[n.label] || "#94a3b8",
    }));

    const graphLinks: GraphViewerLink[] = edges
      .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map((e) => ({
        source: e.source,
        target: e.target,
        relationship: e.relationship,
      }));

    return { nodes: graphNodes, links: graphLinks };
  }, [nodes, edges]);

  // Zoom to fit on data change
  useEffect(() => {
    const timer = setTimeout(() => {
      graphRef.current?.zoomToFit(400, 40);
    }, 500);
    return () => clearTimeout(timer);
  }, [graphData]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleNodeClick = useCallback(
    (node: any) => {
      if (onNodeClick && node.id) {
        onNodeClick(node.id as string);
      }
    },
    [onNodeClick],
  );

  const drawNode = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any, ctx: CanvasRenderingContext2D) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const size = node.val || 4;
      const isCenter = node.id === centerId;

      // Draw node circle
      ctx.beginPath();
      ctx.arc(x, y, size, 0, 2 * Math.PI);
      ctx.fillStyle = node.color;
      ctx.fill();

      if (isCenter) {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Draw label
      const label = node.name || node.id;
      ctx.font = `${isCenter ? "bold " : ""}${Math.max(3, size * 0.8)}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = "#e2e8f0";
      ctx.fillText(label, x, y + size + 2);
    },
    [centerId],
  );

  const drawLink = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (link: any, ctx: CanvasRenderingContext2D) => {
      const source = link.source as GraphViewerNode;
      const target = link.target as GraphViewerNode;
      if (!source.x || !target.x) return;

      // Draw edge line
      ctx.beginPath();
      ctx.moveTo(source.x, source.y ?? 0);
      ctx.lineTo(target.x, target.y ?? 0);
      ctx.strokeStyle = "rgba(148, 163, 184, 0.3)";
      ctx.lineWidth = 0.5;
      ctx.stroke();

      // Draw relationship label at midpoint
      if (link.relationship) {
        const midX = (source.x + target.x) / 2;
        const midY = ((source.y ?? 0) + (target.y ?? 0)) / 2;
        ctx.font = "2px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "rgba(148, 163, 184, 0.5)";
        ctx.fillText(link.relationship, midX, midY);
      }
    },
    [],
  );

  if (nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        No graph data to display
      </div>
    );
  }

  return (
    <ForceGraph2D
      ref={graphRef}
      graphData={graphData}
      width={width}
      height={height}
      backgroundColor="transparent"
      nodeCanvasObject={drawNode}
      linkCanvasObject={drawLink}
      onNodeClick={handleNodeClick}
      nodeLabel={(node: { name?: string; type?: string; connections_count?: number }) =>
        `${node.name ?? ""} (${node.type ?? ""}) - ${node.connections_count ?? 0} connections`
      }
      cooldownTicks={100}
      enableZoomInteraction={true}
      enablePanInteraction={true}
    />
  );
}
