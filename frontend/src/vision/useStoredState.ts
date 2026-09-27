import { useEffect, useState } from 'react';

/** Browser-only persistence for explicitly noncanonical Astra prototype views. */
export function useStoredState<T>(key: string, initial: T): [T, (next: T | ((previous: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const saved = localStorage.getItem(`astra-vision:${key}`);
      return saved ? JSON.parse(saved) as T : initial;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(`astra-vision:${key}`, JSON.stringify(value));
    } catch {
      // Prototype remains usable without browser persistence.
    }
  }, [key, value]);

  return [value, setValue];
}
