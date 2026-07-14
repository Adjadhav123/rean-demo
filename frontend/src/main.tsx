import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ConfigProvider } from "antd";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#1568e0",
          colorSuccess: "#1a9e4a",
          colorError: "#d4380d",
          borderRadius: 10,
          fontSize: 15,
          fontFamily:
            '"Segoe UI", "Inter", -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif',
        },
        components: {
          Button: {
            controlHeightLG: 52,
            fontWeightStrong: 600,
          },
          Card: {
            borderRadiusLG: 14,
          },
        },
      }}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>
);
