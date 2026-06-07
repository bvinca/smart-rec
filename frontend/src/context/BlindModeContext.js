// recruiter toggle: hides PII in UI, scores still show
// UI-only mask; API still returns real data
// real redaction would be backend work
// persisted in localStorage across reloads
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

const STORAGE_KEY = 'smartrec.blindMode';

const BlindModeContext = createContext({
  blindMode: false,
  toggleBlindMode: () => {},
  setBlindMode: () => {},
  maskName: (s) => s,
  maskEmail: (s) => s,
  maskPhone: (s) => s,
  maskInstitution: (s) => s,
});

const _initialFromStorage = () => {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
};

export const BlindModeProvider = ({ children }) => {
  const [blindMode, setBlindModeState] = useState(_initialFromStorage);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, blindMode ? '1' : '0');
    } catch {
      // private browsing? skip the write
    }
  }, [blindMode]);

  const setBlindMode = useCallback((value) => {
    setBlindModeState(Boolean(value));
  }, []);

  const toggleBlindMode = useCallback(() => {
    setBlindModeState((v) => !v);
  }, []);

  // wrap fields without if-checks at call sites
  const maskName = useCallback(
    (s) => (blindMode ? 'Candidate' : s),
    [blindMode],
  );
  const maskEmail = useCallback(
    (s) => (blindMode ? '••••@••••' : s),
    [blindMode],
  );
  const maskPhone = useCallback(
    (s) => (blindMode ? '••• ••• ••••' : s),
    [blindMode],
  );
  const maskInstitution = useCallback(
    (s) => (blindMode ? '[institution hidden]' : s),
    [blindMode],
  );

  const value = {
    blindMode,
    toggleBlindMode,
    setBlindMode,
    maskName,
    maskEmail,
    maskPhone,
    maskInstitution,
  };

  return (
    <BlindModeContext.Provider value={value}>
      {children}
    </BlindModeContext.Provider>
  );
};

export const useBlindMode = () => useContext(BlindModeContext);

export default BlindModeContext;
