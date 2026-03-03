import type { GraphStatsResponse } from "@/api/types";

interface GraphStatsProps {
  stats: GraphStatsResponse;
}

export function GraphStatsPanel({ stats }: GraphStatsProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border p-3">
          <p className="text-2xl font-bold">{stats.total_nodes}</p>
          <p className="text-xs text-muted-foreground">Total Nodes</p>
        </div>
        <div className="rounded-lg border p-3">
          <p className="text-2xl font-bold">{stats.total_relationships}</p>
          <p className="text-xs text-muted-foreground">Total Relationships</p>
        </div>
      </div>

      {Object.keys(stats.node_counts).length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-medium text-muted-foreground">Node Types</h4>
          <div className="space-y-1">
            {Object.entries(stats.node_counts)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => (
                <div key={type} className="flex justify-between text-sm">
                  <span>{type}</span>
                  <span className="font-medium">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {Object.keys(stats.relationship_counts).length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-medium text-muted-foreground">Relationship Types</h4>
          <div className="space-y-1">
            {Object.entries(stats.relationship_counts)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => (
                <div key={type} className="flex justify-between text-sm">
                  <span>{type}</span>
                  <span className="font-medium">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
