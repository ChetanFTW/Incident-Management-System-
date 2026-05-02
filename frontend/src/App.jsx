import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login          from "./pages/Login";
import Dashboard      from "./pages/Dashboard";
import IncidentDetail from "./pages/IncidentDetail";
import RCAForm        from "./pages/RCAForm";

function PrivateRoute({ children }) {
  const { isAuth } = useAuth();
  return isAuth ? children : <Navigate to="/login" replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      <Route path="/incidents/:id" element={<PrivateRoute><IncidentDetail /></PrivateRoute>} />
      <Route path="/incidents/:id/rca" element={<PrivateRoute><RCAForm /></PrivateRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
