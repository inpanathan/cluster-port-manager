import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, BarChart3, Network } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { EmptyState } from "@/components/shared/EmptyState";
import { searchGraph, getEntity, getGraphStats } from "@/api/graph";
import { GraphViewer } from "./GraphViewer";
import { EntityDetail } from "./EntityDetail";
import { GraphStatsPanel } from "./GraphStats";

type ViewMode = "search" | "stats";

export function KnowledgeGraphPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("search");
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Resize observer for graph container
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Search query
  const {
    data: searchResults,
    isLoading: searchLoading,
  } = useQuery({
    queryKey: ["graph-search", submittedQuery],
    queryFn: () => searchGraph({ q: submittedQuery, limit: 30 }),
    enabled: !!submittedQuery,
  });

  // Entity neighborhood
  const {
    data: neighborhood,
    isLoading: neighborhoodLoading,
  } = useQuery({
    queryKey: ["graph-entity", selectedEntityId],
    queryFn: () => getEntity(selectedEntityId!, 2),
    enabled: !!selectedEntityId,
  });

  // Graph stats
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["graph-stats"],
    queryFn: getGraphStats,
    enabled: viewMode === "stats",
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      setSubmittedQuery(searchQuery.trim());
      setSelectedEntityId(null);
      setViewMode("search");
    }
  };

  const handleEntityClick = (entityId: string) => {
    setSelectedEntityId(entityId);
  };

  // Build visualization data
  const graphNodes = neighborhood
    ? [neighborhood.center_node, ...neighborhood.nodes]
    : [];
  const graphEdges = neighborhood?.edges ?? [];
  const selectedEntity = neighborhood?.center_node ?? null;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Knowledge Graph</h1>
            <p className="text-sm text-muted-foreground">
              Explore entities, relationships, and topics across your library
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant={viewMode === "search" ? "default" : "outline"}
              size="sm"
              onClick={() => setViewMode("search")}
            >
              <Search className="mr-1 h-4 w-4" />
              Search
            </Button>
            <Button
              variant={viewMode === "stats" ? "default" : "outline"}
              size="sm"
              onClick={() => setViewMode("stats")}
            >
              <BarChart3 className="mr-1 h-4 w-4" />
              Stats
            </Button>
          </div>
        </div>

        {/* Search bar */}
        <form onSubmit={handleSearch} className="mt-3 flex gap-2">
          <Input
            placeholder="Search entities (e.g., 'machine learning', 'Alan Turing')..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-md"
          />
          <Button type="submit" disabled={!searchQuery.trim()}>
            <Search className="mr-1 h-4 w-4" />
            Search
          </Button>
        </form>
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: search results / stats */}
        <div className="w-72 shrink-0 border-r">
          <ScrollArea className="h-full">
            <div className="p-4">
              {viewMode === "stats" && (
                <>
                  <h2 className="mb-3 text-sm font-semibold">Graph Statistics</h2>
                  {statsLoading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-16 w-full" />
                      <Skeleton className="h-16 w-full" />
                      <Skeleton className="h-32 w-full" />
                    </div>
                  ) : stats ? (
                    <GraphStatsPanel stats={stats} />
                  ) : null}
                </>
              )}

              {viewMode === "search" && (
                <>
                  <h2 className="mb-3 text-sm font-semibold">
                    {submittedQuery
                      ? `Results for "${submittedQuery}"`
                      : "Search Results"}
                    {searchResults && (
                      <span className="ml-1 text-muted-foreground">
                        ({searchResults.total})
                      </span>
                    )}
                  </h2>

                  {searchLoading ? (
                    <div className="space-y-2">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} className="h-14 w-full" />
                      ))}
                    </div>
                  ) : searchResults?.results.length ? (
                    <div className="space-y-1">
                      {searchResults.results.map((result) => (
                        <button
                          key={result.id}
                          onClick={() => handleEntityClick(result.id)}
                          className={`w-full rounded-md px-3 py-2 text-left transition-colors hover:bg-accent ${
                            selectedEntityId === result.id ? "bg-accent" : ""
                          }`}
                        >
                          <p className="text-sm font-medium">{result.name}</p>
                          <div className="mt-0.5 flex items-center gap-1">
                            <Badge variant="outline" className="text-[10px]">
                              {result.type}
                            </Badge>
                            <span className="text-[10px] text-muted-foreground">
                              {result.connections_count} connections
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  ) : submittedQuery ? (
                    <p className="text-sm text-muted-foreground">
                      No entities found matching "{submittedQuery}"
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Search for entities to explore the graph
                    </p>
                  )}
                </>
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Center: graph visualization */}
        <div ref={containerRef} className="flex-1 bg-background">
          {neighborhoodLoading ? (
            <div className="flex h-full items-center justify-center">
              <div className="text-center">
                <Skeleton className="mx-auto h-64 w-64 rounded-full" />
                <p className="mt-4 text-sm text-muted-foreground">Loading graph...</p>
              </div>
            </div>
          ) : selectedEntityId && graphNodes.length > 0 ? (
            <GraphViewer
              nodes={graphNodes}
              edges={graphEdges}
              centerId={selectedEntityId}
              width={dimensions.width}
              height={dimensions.height}
              onNodeClick={handleEntityClick}
            />
          ) : (
            <EmptyState
              icon={Network}
              title="No entity selected"
              description="Search for entities and click one to visualize its neighborhood graph"
            />
          )}
        </div>

        {/* Right panel: entity detail */}
        {selectedEntity && (
          <div className="w-72 shrink-0 border-l">
            <ScrollArea className="h-full">
              <div className="p-4">
                <h2 className="mb-3 text-sm font-semibold">Entity Details</h2>
                <EntityDetail entity={selectedEntity} />

                {neighborhood && neighborhood.nodes.length > 0 && (
                  <>
                    <Separator className="my-4" />
                    <h4 className="mb-2 text-sm font-medium text-muted-foreground">
                      Connected ({neighborhood.nodes.length})
                    </h4>
                    <div className="space-y-1">
                      {neighborhood.nodes.slice(0, 15).map((node) => (
                        <button
                          key={node.id}
                          onClick={() => handleEntityClick(node.id)}
                          className="w-full rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-accent"
                        >
                          <span className="font-medium">{node.name}</span>
                          <Badge variant="outline" className="ml-1 text-[10px]">
                            {node.type || node.label}
                          </Badge>
                        </button>
                      ))}
                      {neighborhood.nodes.length > 15 && (
                        <p className="px-2 text-xs text-muted-foreground">
                          +{neighborhood.nodes.length - 15} more
                        </p>
                      )}
                    </div>
                  </>
                )}
              </div>
            </ScrollArea>
          </div>
        )}
      </div>
    </div>
  );
}
