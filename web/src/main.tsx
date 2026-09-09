import React from "react";
import { createRoot } from "react-dom/client";

const el = document.getElementById("root");
if (!el) throw new Error("#root not found");

createRoot(el).render(
  <React.StrictMode>
    <p>FinHive — scaffold. Routes land in M1a.</p>
  </React.StrictMode>,
);
