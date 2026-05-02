import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { register } from "../api/client";
import "./Login.css";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();

  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (key) => (e) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        await register(form.username, form.email, form.password);
        setMode("login");
        setError("Account created! Please login.");
      } else {
        await login(form.username, form.password);
        nav("/");
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-bg">
      <div className="login-container">
        
        {/* Card */}
        <div className="login-glass">

          {/* Icon */}
          <div className="login-icon">🔐</div>

          <h2 className="login-title">
            {mode === "login" ? "Sign in with email" : "Create account"}
          </h2>

          <p className="login-sub">
            Make a new doc to bring your words, data, and team together.
          </p>

          {error && <div className="login-error">{error}</div>}

          <form onSubmit={submit}>
            
            {/* Username */}
            <input
              type="text"
              placeholder="Username"
              value={form.username}
              onChange={set("username")}
              required
              className="login-input"
            />

            {/* Email */}
            {mode === "register" && (
              <input
                type="email"
                placeholder="Email"
                value={form.email}
                onChange={set("email")}
                required
                className="login-input"
              />
            )}

            {/* Password */}
            <input
              type="password"
              placeholder="Password"
              value={form.password}
              onChange={set("password")}
              required
              className="login-input"
            />

            {/* Button */}
            <button type="submit" disabled={loading} className="login-btn">
              {loading
                ? "Please wait..."
                : mode === "login"
                ? "Get Started"
                : "Register"}
            </button>
          </form>


          {/* Toggle */}
          <p className="login-toggle">
            {mode === "login" ? "No account?" : "Have an account?"}
            <button onClick={() => setMode(mode === "login" ? "register" : "login")}>
              {mode === "login" ? " Register" : " Sign in"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}