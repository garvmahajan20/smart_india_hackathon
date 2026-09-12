import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useMotionValue } from "framer-motion";
import { Link, useLocation } from "react-router-dom";
import {
  ClipboardCheck,
  FilePlus2,
  LayoutDashboard,
  Menu,
  X,
} from "lucide-react";
import { apiClient } from "../../api/client";

export interface iNavItem {
  heading: string;
  href: string;
  subheading?: string;
}

interface iNavLinkProps extends iNavItem {
  setIsActive: (isActive: boolean) => void;
  index: number;
}

interface iHeaderProps {
  navItems?: iNavItem[];
}

const MENU_EASE: [number, number, number, number] = [0.76, 0, 0.24, 1];

const MENU_SLIDE_ANIMATION = {
  initial: { x: "calc(-100% - 100px)" },
  enter: { x: "0", transition: { duration: 0.65, ease: MENU_EASE } },
  exit: {
    x: "calc(-100% - 100px)",
    transition: { duration: 0.5, ease: MENU_EASE },
  },
};

export const defaultNavItems: iNavItem[] = [
  {
    heading: "Dashboard",
    href: "/dashboard",
    subheading: "Procurement verification overview",
  },
  {
    heading: "New Verification",
    href: "/verify/new",
    subheading: "Ingest tender and bidder submissions",
  },
  {
    heading: "Review Queue",
    href: "/review",
    subheading: "Officer adjudication and escalations",
  },
];

const navIcons = [LayoutDashboard, FilePlus2, ClipboardCheck];

export const NavLink: React.FC<iNavLinkProps> = ({
  heading,
  href,
  subheading,
  setIsActive,
  index,
}) => {
  const location = useLocation();
  const ref = useRef<HTMLAnchorElement | null>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const Icon = navIcons[index - 1] || ClipboardCheck;
  const isActive = location.pathname === href;

  const handleMouseMove = (
    e: React.MouseEvent<HTMLAnchorElement, MouseEvent>,
  ) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    x.set((e.clientX - rect.left) / rect.width - 0.5);
    y.set((e.clientY - rect.top) / rect.height - 0.5);
  };

  return (
    <motion.div
      initial="initial"
      whileHover="whileHover"
      className={`group relative border-b py-4 transition-colors duration-300 md:py-5 ${
        isActive ? "border-blue-500/50" : "border-slate-200"
      }`}
    >
      <Link
        ref={ref}
        to={href}
        onMouseMove={handleMouseMove}
        onClick={() => setIsActive(false)}
        className="flex items-center gap-4"
      >
        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border transition-all duration-300 ${
            isActive
              ? "border-blue-200 bg-blue-50 text-blue-700 shadow-sm"
              : "border-slate-200 bg-slate-50 text-slate-500 group-hover:border-blue-200 group-hover:bg-blue-50 group-hover:text-blue-700"
          }`}
        >
          <Icon className="h-4 w-4" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className={`font-mono text-[10px] font-bold ${
                isActive ? "text-blue-600" : "text-slate-400"
              }`}
            >
              0{index}
            </span>
            <motion.span
              variants={{ initial: { x: 0 }, whileHover: { x: 3 } }}
              transition={{ type: "spring", stiffness: 300, damping: 24 }}
              className={`text-sm font-bold tracking-tight ${
                isActive ? "text-slate-950" : "text-slate-800"
              }`}
            >
              {heading}
            </motion.span>
          </div>
          {subheading && (
            <span className="mt-0.5 block text-[10px] leading-4 text-slate-500">
              {subheading}
            </span>
          )}
        </div>

        <span
          className={`h-1.5 w-1.5 rounded-full transition-all duration-300 ${
            isActive
              ? "bg-blue-600 shadow-[0_0_0_4px_rgba(37,99,235,0.10)]"
              : "bg-slate-300 group-hover:bg-blue-400"
          }`}
        />
      </Link>
    </motion.div>
  );
};

export const Curve: React.FC = () => {
  const [height, setHeight] = useState(
    typeof window !== "undefined" ? window.innerHeight : 1000,
  );

  useEffect(() => {
    const handleResize = () => setHeight(window.innerHeight);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const initialPath = `M0 0 L-100 0 L-100 ${height} L0 ${height} Q200 ${height / 2} 0 0`;
  const targetPath = `M0 0 L-100 0 L-100 ${height} L0 ${height} Q0 ${height / 2} 0 0`;

  const curve = {
    initial: { d: initialPath },
    enter: { d: targetPath, transition: { duration: 0.8, ease: MENU_EASE } },
    exit: { d: initialPath, transition: { duration: 0.55, ease: MENU_EASE } },
  };

  return (
    <svg
      className="pointer-events-none absolute -right-[79px] top-0 h-full w-[80px]"
      aria-hidden="true"
    >
      <motion.path variants={curve} initial="initial" animate="enter" exit="exit" fill="#ffffff" />
    </svg>
  );
};

export const CurvedNavbar: React.FC<
  iHeaderProps & { setIsActive: (isActive: boolean) => void }
> = ({ setIsActive, navItems = defaultNavItems }) => {
  const [healthStatus, setHealthStatus] = useState<"connected" | "offline" | "checking">("checking");
  const [healthVersion, setHealthVersion] = useState<string>("1.0.0");

  useEffect(() => {
    let mounted = true;
    apiClient
      .getHealth()
      .then((res) => {
        if (mounted) {
          setHealthStatus("connected");
          setHealthVersion(res.version || "1.0.0");
        }
      })
      .catch(() => {
        if (mounted) setHealthStatus("offline");
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <motion.aside
      variants={MENU_SLIDE_ANIMATION}
      initial="initial"
      animate="enter"
      exit="exit"
      className="fixed left-0 top-0 z-40 h-[100dvh] w-[min(88vw,390px)] bg-white shadow-[12px_0_40px_rgba(15,23,42,0.10)]"
      aria-label="Primary navigation"
    >
      <div className="flex h-full flex-col px-6 pb-6 pt-6 sm:px-8">
        <div className="flex min-h-[44px] items-center border-b border-slate-200 pb-5">
          <div className="pl-12">
            <p className="text-sm font-black tracking-tight text-slate-950">J.A.R.V.I.S</p>
          </div>
        </div>

        <div className="mt-7">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[9px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Workspace
            </span>
            <span className="font-mono text-[9px] text-slate-300">NAV-01</span>
          </div>
          <nav>
            {navItems.map((item, index) => (
              <NavLink
                key={item.href}
                {...item}
                setIsActive={setIsActive}
                index={index + 1}
              />
            ))}
          </nav>
        </div>

        <div className="mt-auto space-y-3 border-t border-slate-200 pt-5">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5">
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${
                  healthStatus === "connected"
                    ? "bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.15)]"
                    : healthStatus === "offline"
                    ? "bg-rose-500 shadow-[0_0_0_4px_rgba(244,63,94,0.15)]"
                    : "bg-amber-500 animate-pulse shadow-[0_0_0_4px_rgba(245,158,11,0.15)]"
                }`}
              />
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-700">
                {healthStatus === "connected"
                  ? "Verification services ready"
                  : healthStatus === "offline"
                  ? "Verification services offline"
                  : "Connecting to services..."}
              </span>
            </div>
            <p className="mt-1.5 text-[10px] leading-4 text-slate-500">
              {healthStatus === "connected"
                ? `Evidence-grounded checks online · FastAPI v${healthVersion}`
                : healthStatus === "offline"
                ? "Backend engine unreachable at http://localhost:8000"
                : "Probing verification engine status..."}
            </p>
          </div>
          <div className="flex items-center justify-between text-[9px] font-mono uppercase tracking-wider text-slate-400">
            <span>GeM verification desk</span>
            <span>v{healthVersion}</span>
          </div>
        </div>
      </div>
      <Curve />
    </motion.aside>
  );
};

export const Header: React.FC<iHeaderProps> = ({ navItems = defaultNavItems }) => {
  const [isActive, setIsActive] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setIsActive((value) => !value)}
        aria-label={isActive ? "Close Navigation Menu" : "Open Navigation Menu"}
        aria-expanded={isActive}
        className="fixed left-3 top-3 z-50 flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-white/95 text-slate-800 shadow-md backdrop-blur transition-all hover:border-blue-200 hover:text-blue-700 sm:left-4 sm:top-4"
      >
        {isActive ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      <AnimatePresence mode="wait">
        {isActive && (
          <CurvedNavbar setIsActive={setIsActive} navItems={navItems} />
        )}
      </AnimatePresence>
    </>
  );
};

export default Header;
