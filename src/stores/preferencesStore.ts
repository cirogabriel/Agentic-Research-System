import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { QueryTransform, RetrievalStrategy } from '@/types/api';


export interface ResearchDefaults {
  max_iterations: number | null;
  token_budget: number | null;
  top_k: number | null;
  retrieval_strategy: RetrievalStrategy | null;
  query_transform: QueryTransform | null;
  parallel: boolean;
  reinvestigate: boolean;
}
export const INITIAL_DEFAULTS: ResearchDefaults = {
  max_iterations: null,
  token_budget: null,
  top_k: null,
  retrieval_strategy: null,
  query_transform: null,
  parallel: true,
  reinvestigate: true,
};

interface PreferencesState {
  sidebarCollapsed: boolean;
  defaults: ResearchDefaults;
  toggleSidebar: () => void;
  setDefaults: (d: ResearchDefaults) => void;
  resetDefaults: () => void;
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      defaults: INITIAL_DEFAULTS,
      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setDefaults: (defaults) => set({ defaults }),
      resetDefaults: () => set({ defaults: INITIAL_DEFAULTS }),
    }),
    { name: 'ars.preferences' },
  ),
);
