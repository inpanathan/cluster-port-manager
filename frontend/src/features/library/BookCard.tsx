import { MoreVertical, Download, Trash2, BookOpen, Loader2 } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { BookSummary } from "@/api/types";
import { deleteBook, getBookDownloadUrl, getBookCoverUrl } from "@/api/books";

interface BookCardProps {
  book: BookSummary;
  onClick: () => void;
}

const statusColors: Record<string, string> = {
  completed: "bg-green-500",
  processing: "bg-yellow-500",
  pending: "bg-gray-400",
  failed: "bg-red-500",
};

export function BookCard({ book, onClick }: BookCardProps) {
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => deleteBook(book.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["books"] }),
  });

  const hasCover = !!book.cover_image_path;

  return (
    <Card
      className="cursor-pointer overflow-hidden transition-shadow hover:shadow-md"
      onClick={onClick}
    >
      {/* Cover image area */}
      <div className="relative h-48 bg-muted">
        {hasCover ? (
          <img
            src={getBookCoverUrl(book.id)}
            alt={book.title}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <BookOpen className="h-16 w-16 text-muted-foreground/30" />
          </div>
        )}
        {/* Format badge */}
        <Badge
          variant="secondary"
          className="absolute bottom-2 right-2 uppercase text-xs"
        >
          {book.file_format}
        </Badge>
      </div>

      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-sm font-medium">{book.title}</h3>
            {book.author && (
              <p className="mt-0.5 truncate text-xs text-muted-foreground">{book.author}</p>
            )}
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="ml-1 h-7 w-7 shrink-0">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem asChild>
                <a href={getBookDownloadUrl(book.id)} download>
                  <Download className="mr-2 h-4 w-4" />
                  Download
                </a>
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-destructive"
                onClick={() => deleteMutation.mutate()}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
          {book.publication_year && <span>{book.publication_year}</span>}
          {book.publication_year && <span>&middot;</span>}
          <div className="flex items-center gap-1">
            {book.embedding_status === "processing" ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <div className={`h-1.5 w-1.5 rounded-full ${statusColors[book.embedding_status] ?? "bg-gray-400"}`} />
            )}
            <span className="capitalize">{book.embedding_status}</span>
          </div>
          {book.embedding_status === "completed" && book.chunk_count != null && (
            <>
              <span>&middot;</span>
              <span>{book.chunk_count} chunks</span>
            </>
          )}
        </div>

        {book.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {book.tags.slice(0, 3).map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
            {book.tags.length > 3 && (
              <Badge variant="outline" className="text-xs">
                +{book.tags.length - 3}
              </Badge>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
