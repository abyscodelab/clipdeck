"use client";

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  isAuthenticated as checkIsAuth,
  getAccessToken,
  setTokens,
  clearTokens,
  isBrowser,
} from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import type { User, LoginResponse } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  mustChangePassword: boolean;
  login: (username: string, password: string, totpCode?: string) => Promise<LoginResponse>;
  logout: () => void;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = React.useState<boolean>(false);
  const [isLoading, setIsLoading] = React.useState<boolean>(true);
  const [mustChangePassword, setMustChangePassword] = React.useState<boolean>(false);
  const router = useRouter();
  const pathname = usePathname();

  const fetchCurrentUser = React.useCallback(async () => {
    try {
      if (!checkIsAuth()) {
        setUser(null);
        setIsAuthenticated(false);
        setIsLoading(false);
        return;
      }

      setIsAuthenticated(true);
      const userData = await api.auth.me();
      setUser(userData);
      setMustChangePassword(userData.must_change_password);
    } catch (err) {
      console.warn("Failed to fetch user:", err);
      if (err instanceof ApiError && err.status === 401) {
        clearTokens();
        setUser(null);
        setIsAuthenticated(false);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchCurrentUser();

    const handleAuthChange = () => {
      fetchCurrentUser();
    };

    if (isBrowser()) {
      window.addEventListener("clipdeck_auth_change", handleAuthChange);
    }

    return () => {
      if (isBrowser()) {
        window.removeEventListener("clipdeck_auth_change", handleAuthChange);
      }
    };
  }, [fetchCurrentUser]);

  const login = async (username: string, password: string, totpCode?: string) => {
    setIsLoading(true);
    try {
      const res = await api.auth.login(username, password, totpCode);
      setTokens(res.access_token, res.refresh_token);
      setIsAuthenticated(true);
      setMustChangePassword(res.must_change_password);
      await fetchCurrentUser();
      return res;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    clearTokens();
    setUser(null);
    setIsAuthenticated(false);
    setMustChangePassword(false);
    router.push("/login");
  };

  const changePassword = async (currentPassword: string, newPassword: string) => {
    await api.auth.changePassword(currentPassword, newPassword);
    setMustChangePassword(false);
    if (user) {
      setUser({ ...user, must_change_password: false });
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        mustChangePassword,
        login,
        logout,
        changePassword,
        refreshUser: fetchCurrentUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
