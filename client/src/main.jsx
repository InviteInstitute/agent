import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/open-sans/400.css";
import "@fontsource/open-sans/600.css";
import "@fontsource/open-sans/700.css";
import "@fontsource/open-sans/800.css";
import "./styles/app.css";
import App from "./App.jsx";
import TurnstileGate from "./TurnstileGate.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <TurnstileGate />
    <App />
  </React.StrictMode>,
);
