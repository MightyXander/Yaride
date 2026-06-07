import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { UserProvider } from "./state/UserContext";
import { FlowProvider } from "./state/FlowContext";
import { initTelegram } from "./telegram/webapp";
import "./index.css";

initTelegram();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <UserProvider>
        <FlowProvider>
          <App />
        </FlowProvider>
      </UserProvider>
    </BrowserRouter>
  </StrictMode>,
);
