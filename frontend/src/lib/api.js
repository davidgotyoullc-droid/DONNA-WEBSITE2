import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

export const api = axios.create({ baseURL: API, withCredentials: true, timeout: 15000 });

// A static host answers unknown paths with index.html (SPA fallback). Treat
// non-JSON responses as failures so callers fall back instead of crashing.
api.interceptors.response.use(
  (res) => {
    const ct = res.headers["content-type"] || "";
    if (!ct.includes("application/json")) {
      return Promise.reject(new Error("Backend unreachable: expected JSON, got HTML"));
    }
    return res;
  },
  (err) => Promise.reject(err),
);

export const formatPrice = (cents) =>
  `$${(cents / 100).toFixed(2).replace(/\.00$/, ".00")}`;
