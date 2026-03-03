import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppLayout } from "@/components/layout/AppLayout";
import { ChatPage } from "@/features/chat/ChatPage";
import { SourcesPage } from "@/features/sources/SourcesPage";
import { SummarizePage } from "@/features/summarize/SummarizePage";
import { QnAPage } from "@/features/qna/QnAPage";
import { InterviewPage } from "@/features/interview/InterviewPage";
import { LibraryPage } from "@/features/library/LibraryPage";
import { KnowledgeGraphPage } from "@/features/graph/KnowledgeGraphPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<Navigate to="/chat" replace />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="chat/:sessionId" element={<ChatPage />} />
              <Route path="sources" element={<SourcesPage />} />
              <Route path="summarize" element={<SummarizePage />} />
              <Route path="qna" element={<QnAPage />} />
              <Route path="interview" element={<InterviewPage />} />
              <Route path="interview/:sessionId" element={<InterviewPage />} />
              <Route path="library" element={<LibraryPage />} />
              <Route path="graph" element={<KnowledgeGraphPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
