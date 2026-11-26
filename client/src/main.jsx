import React from "react";
import ReactDOM from "react-dom/client";
import "./styles/carbon.scss";
import "./styles/app.css";
import App from "./App.jsx";
import TurnstileGate from "./TurnstileGate.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <TurnstileGate />
    <App />
  </React.StrictMode>,
);
