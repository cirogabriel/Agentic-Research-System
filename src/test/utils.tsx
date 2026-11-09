import type { ReactElement } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { DocumentOut, ResearchOut } from '@/types/api';

export function renderWithProviders(
  ui: ReactElement,
  opts: { route?: string; path?: string; extraRoutes?: ReactElement } = {},
) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
  const { route = '/', path = '*' } = opts;
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path={path} element={ui} />
            {opts.extraRoutes}
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

export const makeResearch = (over: Partial<ResearchOut> = {}): ResearchOut => ({
  id: 'r1',
  parent_id: null,
  query: 'Investiga las causas de los terremotos en los Andes',
  status: 'completed',
  current_stage: null,
  stop_reason: null,
  clarification_questions: null,
  iterations: 1,
  tokens_input: 1200,
  tokens_output: 300,
  cost_usd: 0.0004,
  created_at: '2026-11-05T10:00:00Z',
  finished_at: '2026-11-05T10:02:10Z',
  ...over,
});

export const makeDocument = (over: Partial<DocumentOut> = {}): DocumentOut => ({
  id: 'd1',
  filename: 'andes.pdf',
  file_type: 'pdf',
  title: 'Seismicity and the Andes',
  author: 'J. Ramos',
  document_date: null,
  size_bytes: 2048,
  content_hash: 'abcdef0123456789abcdef',
  version: 1,
  status: 'indexed',
  error: null,
  num_pages: 12,
  num_chunks: 40,
  created_at: '2026-11-04T10:00:00Z',
  updated_at: '2026-11-04T10:00:00Z',
  indexed_at: '2026-11-04T10:01:00Z',
  ...over,
});
