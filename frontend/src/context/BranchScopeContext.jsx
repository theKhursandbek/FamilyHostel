/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useCallback, useMemo, useState } from "react";
import PropTypes from "prop-types";

/**
 * BranchScopeContext — lift branch-picker state into the fixed Header.
 *
 * Pages that own a branch scope call register/unregister so the Header can
 * render <BranchSelector> next to the user account pill on every route.
 */

const BranchScopeContext = createContext(null);

export function BranchScopeProvider({ children }) {
  const [scope, setScope] = useState(null);

  const register = useCallback((value, onChange) => {
    setScope({ value, onChange });
  }, []);

  const unregister = useCallback(() => {
    setScope(null);
  }, []);

  const ctx = useMemo(
    () => ({ scope, register, unregister }),
    [scope, register, unregister]
  );

  return (
    <BranchScopeContext.Provider value={ctx}>
      {children}
    </BranchScopeContext.Provider>
  );
}

BranchScopeProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export function useBranchScope() {
  const ctx = useContext(BranchScopeContext);
  if (!ctx) throw new Error("useBranchScope must be used within BranchScopeProvider");
  return ctx;
}
