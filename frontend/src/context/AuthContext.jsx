import { createContext, useContext, useState, useCallback } from "react";
import { login as apiLogin } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("ims_token"));
  const [user, setUser]   = useState(() => {
    const t = localStorage.getItem("ims_token");
    if (!t) return null;
    try {
      return JSON.parse(atob(t.split(".")[1]));
    } catch { return null; }
  });

  const login = useCallback(async (username, password) => {
    const { data } = await apiLogin(username, password);
    localStorage.setItem("ims_token", data.access_token);
    setToken(data.access_token);
    const payload = JSON.parse(atob(data.access_token.split(".")[1]));
    setUser(payload);
    return payload;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("ims_token");
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isAuth: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
