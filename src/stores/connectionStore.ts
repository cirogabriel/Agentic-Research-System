import { create } from 'zustand';

const KEY = 'ars.apiKey';
const read = (): string | null => {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
};

interface ConnectionState {
  apiKey: string | null;
  authRequired: boolean;
  setApiKey: (key: string | null) => void;
  markAuthRequired: () => void;
}


export const useConnectionStore = create<ConnectionState>((set) => ({
  apiKey: read(),
  authRequired: false,
  setApiKey: (key) => {
    try {
      if (key) sessionStorage.setItem(KEY, key);
      else sessionStorage.removeItem(KEY);
    } catch {
      /* almacenamiento no disponible */
    }
    set({ apiKey: key, authRequired: false });
  },
  markAuthRequired: () => set({ authRequired: true }),
}));
