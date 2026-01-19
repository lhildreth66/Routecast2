/**
 * Entitlements Provider
 * 
 * React context provider for entitlement state.
 * Wraps the app to make entitlement status available everywhere.
 */

import React, { createContext, useContext } from 'react';
import { useEntitlements } from './useEntitlements';
import type { Entitlement } from './types';

interface EntitlementsContextValue {
  entitlement: Entitlement | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  isPro: boolean;
}

const EntitlementsContext = createContext<EntitlementsContextValue | null>(null);

export function EntitlementsProvider({ children }: { children: React.ReactNode }) {
  const { entitlement, isLoading, error, refresh } = useEntitlements();
  
  const value: EntitlementsContextValue = {
    entitlement,
    isLoading,
    error,
    refresh,
    isPro: entitlement?.isPro === true,
  };
  
  return (
    <EntitlementsContext.Provider value={value}>
      {children}
    </EntitlementsContext.Provider>
  );
}

export function useEntitlementsContext() {
  const context = useContext(EntitlementsContext);
  if (!context) {
    throw new Error('useEntitlementsContext must be used within EntitlementsProvider');
  }
  return context;
}
