import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "./Navbar.css";

export default function Navbar({ wsConnected }) {
  const { user, logout } = useAuth();

  return (
    <nav className="navbar">
      
      {/* Left */}
      <div className="nav-left">
        <Link to="/" className="nav-logo">
          ⚡ IMS
        </Link>

        <Link to="/" className="nav-link">
          Dashboard
        </Link>
      </div>

      {/* Right */}
      <div className="nav-right">

        {/* WebSocket Status */}
        <div className="nav-status">
          <span
            className={`status-dot ${
              wsConnected ? "status-live" : "status-offline"
            }`}
          />
          <span>
            {wsConnected ? "Live" : "Connecting..."}
          </span>
        </div>

        {/* User */}
        {user && (
          <span className="nav-user">
            {user.username}
          </span>
        )}

        {/* Logout */}
        <button onClick={logout} className="nav-logout">
          Logout
        </button>
      </div>
    </nav>
  );
}