import React, { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { User, ChevronRight } from "lucide-react";
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
        if (mounted) setBackendStatus("offline");
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
      <div className="pointer-events-none fixed inset-0 z-0">
        <GradientBackground />
      </div>

      <Header />

      <div className="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="z-20 flex h-16 shrink-0 items-center justify-between border-b border-slate-200/80 bg-white/95 px-5 pl-20 shadow-sm backdrop-blur sm:pl-24 lg:px-6 lg:pl-24">
          <div className="flex min-w-0 items-center gap-3">
            <span className="hidden text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400 md:inline">
              J.A.R.V.I.S
            </span>
            <ChevronRight className="hidden h-3.5 w-3.5 text-slate-300 md:inline" />
            <h2 className="truncate text-sm font-bold tracking-tight text-slate-900 sm:text-base">
              {getPageTitle(location.pathname)}
            </h2>
          </div>

          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            <div className="hidden items-center gap-2.5 border-l border-slate-200 pl-3 sm:flex">
              <div className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-500">
                <User className="h-4 w-4" />
              </div>
              <div className="text-left">
                <span className="block text-[11px] font-bold leading-none text-slate-800">
                  Procurement Officer
                </span>
                <span className="mt-1 block font-mono text-[9px] text-slate-400">
                  Officer Desk #4
                </span>
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 focus:outline-none sm:p-5 lg:p-6" tabIndex={-1}>
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
