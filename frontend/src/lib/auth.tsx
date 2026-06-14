"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { getMySalon, type Salon } from "./api";

type AuthState = {
  salon: Salon | null;
  apiKey: string | null;
  isLoading: boolean;
  login: (apiKey: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

const STORAGE_KEY = "ping_auth";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [salon, setSalon] = useState<Salon | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const { salon, apiKey } = JSON.parse(stored);
        setSalon(salon);
        setApiKey(apiKey);
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
    setIsLoading(false);
  }, []);

  const login = async (key: string) => {
    const data = await getMySalon(key); // throws ApiError on bad key
    setSalon(data);
    setApiKey(key);
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ salon: data, apiKey: key }));
  };

  const logout = () => {
    setSalon(null);
    setApiKey(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  return (
    <AuthContext.Provider value={{ salon, apiKey, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
