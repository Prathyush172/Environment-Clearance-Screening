import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export interface User {
  id: string;
  email: string;
  username: string;
  full_name?: string;
  role: string;
  client_id: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (usernameOrEmail: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string, fullName?: string, clientId?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("eia_auth_token"));
  const [loading, setLoading] = useState<boolean>(true);

  // Validate or restore session on load
  useEffect(() => {
    let isSubscribed = true;
    const restoreSession = async () => {
      const storedToken = localStorage.getItem("eia_auth_token");
      if (!storedToken) {
        if (isSubscribed) setLoading(false);
        return;
      }

      try {
        const res = await fetch("/api/v1/auth/me", {
          headers: { "Authorization": `Bearer ${storedToken}` },
          credentials: "include",
        });
        if (res.ok) {
          const userData = await res.json();
          if (isSubscribed) {
            setUser(userData);
            setToken(storedToken);
          }
        } else {
          // Token invalid or expired
          localStorage.removeItem("eia_auth_token");
          localStorage.removeItem("eia_auth_user");
          if (isSubscribed) {
            setUser(null);
            setToken(null);
          }
        }
      } catch {
        // Fallback to cached user if offline
        const cachedUser = localStorage.getItem("eia_auth_user");
        if (cachedUser && isSubscribed) {
          try {
            setUser(JSON.parse(cachedUser));
          } catch {}
        }
      } finally {
        if (isSubscribed) setLoading(false);
      }
    };

    restoreSession();
    return () => { isSubscribed = false; };
  }, []);

  const login = async (usernameOrEmail: string, password: string) => {
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username_or_email: usernameOrEmail, password }),
      credentials: "include",
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Login failed with status ${res.status}`);
    }

    const data = await res.json();
    setToken(data.access_token);
    setUser(data.user);
    localStorage.setItem("eia_auth_token", data.access_token);
    localStorage.setItem("eia_auth_user", JSON.stringify(data.user));
    if (data.user.client_id) {
      localStorage.setItem("eia_client_id", data.user.client_id);
    }
  };

  const register = async (email: string, username: string, password: string, fullName?: string, clientId?: string) => {
    const res = await fetch("/api/v1/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        username,
        password,
        full_name: fullName || undefined,
        client_id: clientId || undefined,
      }),
      credentials: "include",
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Registration failed with status ${res.status}`);
    }

    const data = await res.json();
    setToken(data.access_token);
    setUser(data.user);
    localStorage.setItem("eia_auth_token", data.access_token);
    localStorage.setItem("eia_auth_user", JSON.stringify(data.user));
    if (data.user.client_id) {
      localStorage.setItem("eia_client_id", data.user.client_id);
    }
  };

  const logout = async () => {
    try {
      const storedToken = localStorage.getItem("eia_auth_token");
      if (storedToken) {
        await fetch("/api/v1/auth/logout", {
          method: "POST",
          headers: { "Authorization": `Bearer ${storedToken}` },
          credentials: "include",
        });
      }
    } catch {
      // Best-effort server notification
    } finally {
      setUser(null);
      setToken(null);
      localStorage.removeItem("eia_auth_token");
      localStorage.removeItem("eia_auth_user");
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
