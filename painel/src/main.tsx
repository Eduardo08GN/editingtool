import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource/public-sans/400.css";
import "@fontsource/public-sans/500.css";
import "@fontsource/public-sans/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "./tokens.css";
import "./estilo.css";
import { App } from "./App";

createRoot(document.getElementById("raiz")!).render(<StrictMode><App /></StrictMode>);
