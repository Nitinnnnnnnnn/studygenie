import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('studygenie_user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem('studygenie_token') || null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const verifyToken = async () => {
      if (token) {
        try {
          const res = await api.get('/auth/me');
          setUser(res.data);
          localStorage.setItem('studygenie_user', JSON.stringify(res.data));
        } catch (err) {
          logout();
        }
      }
      setIsLoading(false);
    };

    verifyToken();

    const handleForceLogout = () => logout();
    window.addEventListener('studygenie_logout', handleForceLogout);
    return () => window.removeEventListener('studygenie_logout', handleForceLogout);
  }, [token]);

  const login = async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    const { access_token, user: loggedUser } = res.data;
    setToken(access_token);
    setUser(loggedUser);
    localStorage.setItem('studygenie_token', access_token);
    localStorage.setItem('studygenie_user', JSON.stringify(loggedUser));
    return loggedUser;
  };

  const register = async (email, password, fullName) => {
    const res = await api.post('/auth/register', { email, password, full_name: fullName });
    const { access_token, user: newUser } = res.data;
    setToken(access_token);
    setUser(newUser);
    localStorage.setItem('studygenie_token', access_token);
    localStorage.setItem('studygenie_user', JSON.stringify(newUser));
    return newUser;
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('studygenie_token');
    localStorage.removeItem('studygenie_user');
  };

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated: !!token, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
