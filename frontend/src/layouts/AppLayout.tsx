import React, { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import {
  User,
  ChevronRight,
  Shield,
} from "lucide-react";
import { apiClient } from "../api/client";
import Header from "../components/common/CurvedMenu";
import { GradientBackground } from "../components/common/GradientBackground";

export const AppLayout: React.FC = () => {
  const location = useLocation();
  const [backendStatus, setBackendStatus] = useState<"connected" | "offline" | "checking">("checking");
  const [backendVersion, setBackendVersion] = useState<string>("1.0.0");

  useEffect(() => {
    let mounted = true;
    apiClient
      .getHealth()
      .then((res) => {
        if (mounted) {
          setBackendStatus("connected");
          setBackendVersion(res.version || "1.0.0");
        }
      })
      .catch(() => {
        if (mounted) {
          setBackendStatus("offline");
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const getPageTitle = (path: string) => {
    if (path.startsWith("/verify/new")) return "New Bid Verification";
    if (path.startsWith("/verification")) return "Verification Analysis & Dossier";
    if (path.startsWith("/review")) return "Officer Review Queue";
    return "Procurement Verification Dashboard";
  };

  return (
    <div className="relative flex h-screen w-full overflow-hidden font-sans">
      {/* Marine Horizon — ENTIRE WEBSITE Background */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <GradientBackground />
      </div>

      {/* 21st.dev CURVED MENU (Left-Anchored Production Navigation) */}
      <Header />

      {/* MAIN APPLICATION VIEW AREA */}
      <div className="relative z-10 flex-1 flex flex-col min-w-0 overflow-hidden w-full">
        {/* Top Header */}
        <header className="h-16 bg-white/95 border-b border-slate-200/80 px-6 pl-20 sm:pl-24 flex items-center justify-between shrink-0 shadow-sm z-10">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-xs shadow-xs hidden sm:flex">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider hidden md:inline">
              GeM Platform
            </span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-400 hidden md:inline" />
            <h2 className="text-base font-bold text-slate-900 truncate">
              {getPageTitle(location.pathname)}
            </h2>
          </div>

          <div className="flex items-center gap-3">
            {/* Connectivity Status */}
            <div className="flex items-center gap-2 px-2.5 py-1 bg-slate-100 rounded-md border border-slate-200 text-[11px]">
              <span
                className={`w-2 h-2 rounded-full ${
                  backendStatus === "connected"
                    ? "bg-emerald-500 ring-2 ring-emerald-500/20"
                    : backendStatus === "checking"
                    ? "bg-amber-500 animate-pulse"
                    : "bg-rose-500 ring-2 ring-rose-500/20"
                }`}
              />
              <span className="text-slate-700 font-medium hidden lg:inline">
                {backendStatus === "connected"
                  ? "Backend Connected"
                  : backendStatus === "checking"
                  ? "Connecting..."
                  : "Backend Offline"}
              </span>
              <span className="font-mono text-[10px] text-slate-500">v{backendVersion}</span>
            </div>

            {/* Demo Mode Badge */}
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-300 tracking-wider">
              LOCAL DEMO
            </span>

            {/* Officer Profile Stub */}
            <div className="flex items-center gap-2.5 pl-3 border-l border-slate-200">
              <div className="w-7 h-7 rounded-full bg-slate-100 border border-slate-300 flex items-center justify-center text-slate-600">
                <User className="w-4 h-4" />
              </div>
              <div className="text-left hidden sm:block">
                <span className="block text-xs font-semibold text-slate-800 leading-none">
                  Procurement Officer
                </span>
                <span className="block text-[10px] text-slate-500 font-mono mt-0.5">
                  Officer Desk #4
                </span>
              </div>
            </div>
          </div>
        </header>

        {/* Dynamic Page Content */}
        <main className="flex-1 overflow-y-auto p-6 focus:outline-none" tabIndex={-1}>
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
