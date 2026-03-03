import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { GraphNode } from "@/api/types";

interface EntityDetailProps {
  entity: GraphNode;
}

export function EntityDetail({ entity }: EntityDetailProps) {
  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-lg font-semibold">{entity.name}</h3>
        <div className="mt-1 flex items-center gap-2">
          <Badge variant="secondary">{entity.type || entity.label}</Badge>
          <span className="text-xs text-muted-foreground">
            {entity.connections_count} connections
          </span>
        </div>
      </div>

      <Separator />

      {Object.keys(entity.properties).length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-muted-foreground">Properties</h4>
          <dl className="space-y-1">
            {Object.entries(entity.properties).map(([key, value]) => (
              <div key={key} className="flex gap-2 text-sm">
                <dt className="font-medium text-muted-foreground">{key}:</dt>
                <dd className="text-foreground">{String(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}
