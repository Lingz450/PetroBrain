import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

import type { Module, Principal } from '@petrobrain/types';

import { decodePrincipal } from './jwt.js';

export type ThinkingMode = 'instant' | 'default' | 'extended';

/**
 * Resolve the API base URL. In dev the localhost fallback is fine; in any
 * non-dev build we refuse to fall back so a deploy that forgot to set
 * NEXT_PUBLIC_API_BASE_URL fails loudly rather than silently calling
 * http://localhost:8000 from a customer browser.
 */
function resolveApiBaseUrl(): string {
  const runtime =
    typeof window !== 'undefined'
      ? (window as Window & { __PB_API__?: string }).__PB_API__
      : undefined;
  const env = process.env.NEXT_PUBLIC_API_BASE_URL;
  const resolved = runtime ?? env;
  if (resolved) return resolved;
  const nodeEnv = process.env.NODE_ENV;
  if (nodeEnv && nodeEnv !== 'development' && nodeEnv !== 'test') {
    throw new Error(
      'NEXT_PUBLIC_API_BASE_URL is not set. Refusing to fall back to ' +
        'http://localhost:8000 in a non-development build.',
    );
  }
  return 'http://localhost:8000';
}

interface ChatStoreState {
  token: string | null;
  principal: Principal | null;
  module: Module;
  assetContext: string | null;
  thinkingMode: ThinkingMode;
  apiBaseUrl: string;
  /** Default true. Composer + menu lets the user disable for the next turn. */
  webSearchEnabled: boolean;
  /**
   * One-shot toggle: when true, the next assistant message auto-opens in canvas
   * regardless of length. ChatClient resets it once consumed.
   */
  forceCanvasNext: boolean;
  /** When true, the chat sidebar collapses to a 3.5rem icon-only rail. */
  sidebarCollapsed: boolean;
  /**
   * False until zustand finishes hydrating from sessionStorage. Used by the
   * top-level chat surface to suppress the "Sign in" gate flash on a reload
   * while the persisted token is still being read.
   */
  hasHydrated: boolean;
  setToken: (token: string | null) => void;
  setModule: (m: Module) => void;
  setAssetContext: (asset: string | null) => void;
  setThinkingMode: (m: ThinkingMode) => void;
  setWebSearchEnabled: (enabled: boolean) => void;
  setForceCanvasNext: (force: boolean) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

/**
 * Session state lives in sessionStorage - the token never touches localStorage
 * (would survive tab close) and never goes to the server (server verifies a
 * fresh Authorization header on every API call).
 */
export const useChatStore = create<ChatStoreState>()(
  persist(
    (set) => ({
      token: null,
      principal: null,
      module: 'general',
      assetContext: null,
      thinkingMode: 'default',
      apiBaseUrl: resolveApiBaseUrl(),
      webSearchEnabled: true,
      forceCanvasNext: false,
      sidebarCollapsed: false,
      hasHydrated: false,
      setToken: (token) => set({ token, principal: decodePrincipal(token) }),
      setModule: (module) => set({ module }),
      setAssetContext: (assetContext) => set({ assetContext }),
      setThinkingMode: (thinkingMode) => set({ thinkingMode }),
      setWebSearchEnabled: (webSearchEnabled) => set({ webSearchEnabled }),
      setForceCanvasNext: (forceCanvasNext) => set({ forceCanvasNext }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
    }),
    {
      name: 'petrobrain-chat',
      storage: createJSONStorage(() => {
        if (typeof window === 'undefined') {
          // SSR no-op stub. The browser session takes over on hydrate.
          const stub: Storage = {
            length: 0,
            clear() {},
            getItem() { return null; },
            key() { return null; },
            removeItem() {},
            setItem() {},
          };
          return stub;
        }
        return window.sessionStorage;
      }),
      partialize: (s) => ({
        token: s.token,
        principal: s.principal,
        module: s.module,
        assetContext: s.assetContext,
        thinkingMode: s.thinkingMode,
        webSearchEnabled: s.webSearchEnabled,
        sidebarCollapsed: s.sidebarCollapsed,
        // forceCanvasNext is intentionally NOT persisted - it's a one-shot
        // intent for the next send; reload should not silently force-open the
        // canvas on the next turn.
      }),
      onRehydrateStorage: () => (state) => {
        // Re-derive the principal in case the persisted shape predates a schema bump.
        if (state?.token) state.principal = decodePrincipal(state.token);
        if (state) state.hasHydrated = true;
      },
    },
  ),
);
