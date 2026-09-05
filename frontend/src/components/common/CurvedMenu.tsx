import React, { useState, useRef, useEffect } from "react";
import { motion, useMotionValue, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import { Linkedin, Github, Dribbble, Figma } from "lucide-react";

export interface iNavItem {
  heading: string;
  href: string;
  subheading?: string;
  imgSrc?: string;
}

interface iNavLinkProps extends iNavItem {
  setIsActive: (isActive: boolean) => void;
  index: number;
}

interface iCurvedNavbarProps {
  setIsActive: (isActive: boolean) => void;
  navItems: iNavItem[];
}

interface iHeaderProps {
  navItems?: iNavItem[];
  footer?: React.ReactNode;
}

const MENU_EASE: [number, number, number, number] = [0.76, 0, 0.24, 1];

const MENU_SLIDE_ANIMATION = {
  initial: { x: "calc(-100% - 100px)" },
  enter: { x: "0", transition: { duration: 0.8, ease: MENU_EASE } },
  exit: {
    x: "calc(-100% - 100px)",
    transition: { duration: 0.8, ease: MENU_EASE },
  },
};

export const defaultNavItems: iNavItem[] = [
  {
    heading: "Dashboard",
    href: "/dashboard",
    subheading: "Procurement Verification Overview",
  },
  {
    heading: "New Verification",
    href: "/verify/new",
    subheading: "Upload tender and bid dossier",
  },
  {
    heading: "Review Queue",
    href: "/review",
    subheading: "Officer Review Queue & Flags",
  },
];

export const CustomFooter: React.FC = () => {
  return (
    <div className="flex w-full text-sm justify-between text-black px-10 md:px-24 py-5">
      <a href="https://linkedin.com" target="_blank" rel="noopener noreferrer">
        <Linkedin size={24} />
      </a>
      <a href="https://github.com" target="_blank" rel="noopener noreferrer">
        <Github size={24} />
      </a>
      <a href="https://dribbble.com" target="_blank" rel="noopener noreferrer">
        <Dribbble size={24} />
      </a>
      <a href="https://www.figma.com" target="_blank" rel="noopener noreferrer">
        <Figma size={24} />
      </a>
      <a href="https://www.figma.com" target="_blank" rel="noopener noreferrer">
        <Figma size={24} />
      </a>
    </div>
  );
};

export const NavLink: React.FC<iNavLinkProps> = ({
  heading,
  href,
  setIsActive,
  index,
}) => {
  const ref = useRef<HTMLAnchorElement | null>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const handleMouseMove = (
    e: React.MouseEvent<HTMLAnchorElement, MouseEvent>,
  ) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    x.set(mouseX / rect.width - 0.5);
    y.set(mouseY / rect.height - 0.5);
  };

  const handleClick = () => {
    return setIsActive(false);
  };

  const isExternalLink = href.startsWith("http");
  const linkProps = isExternalLink
    ? { target: "_blank", rel: "noopener noreferrer" }
    : {};

  return (
    <motion.div
      onClick={handleClick}
      initial="initial"
      whileHover="whileHover"
      className="group relative flex items-center justify-between border-b border-black/30 py-4 transition-colors duration-500 md:py-8 uppercase"
      {...linkProps}
    >
      <Link ref={ref} onMouseMove={handleMouseMove} to={href}>
        <div className="relative flex items-start">
          <span className="text-black transition-colors duration-500 text-2xl font-thin mr-2">
            {index}.
          </span>
          <div className="flex flex-row gap-2">
            <motion.span
              variants={{
                initial: { x: 0 },
                whileHover: { x: -16 },
              }}
              transition={{
                type: "spring",
                staggerChildren: 0.075,
                delayChildren: 0.25,
              }}
              className="relative z-10 block text-2xl font-extralight text-black transition-colors duration-500 md:text-2xl"
            >
              {heading.split("").map((letter, i) => {
                return (
                  <motion.span
                    key={i}
                    variants={{
                      initial: { x: 0 },
                      whileHover: { x: 16 },
                    }}
                    transition={{ type: "spring" }}
                    className="inline-block"
                  >
                    {letter === " " ? "\u00A0" : letter}
                  </motion.span>
                );
              })}
            </motion.span>
          </div>
        </div>
      </Link>
    </motion.div>
  );
};

export const Curve: React.FC = () => {
  const [height, setHeight] = useState(
    typeof window !== "undefined" ? window.innerHeight : 1000
  );

  useEffect(() => {
    const handleResize = () => {
      setHeight(window.innerHeight);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const initialPath = `M0 0 L-100 0 L-100 ${height} L0 ${height} Q200 ${height / 2} 0 0`;
  const targetPath = `M0 0 L-100 0 L-100 ${height} L0 ${height} Q0 ${height / 2} 0 0`;

  const curve = {
    initial: { d: initialPath },
    enter: {
      d: targetPath,
      transition: { duration: 1, ease: MENU_EASE },
    },
    exit: {
      d: initialPath,
      transition: { duration: 0.8, ease: MENU_EASE },
    },
  };

  return (
    <svg
      className="absolute top-0 -right-[99px] w-[100px] stroke-none h-full pointer-events-none"
      style={{ fill: "#ffffff" }}
    >
      <motion.path
        variants={curve}
        initial="initial"
        animate="enter"
        exit="exit"
      />
    </svg>
  );
};

export const CurvedNavbar: React.FC<
  iCurvedNavbarProps & { footer?: React.ReactNode }
> = ({ setIsActive, navItems, footer }) => {
  return (
    <motion.div
      variants={MENU_SLIDE_ANIMATION}
      initial="initial"
      animate="enter"
      exit="exit"
      className="h-[100dvh] w-screen max-w-screen-sm fixed left-0 top-0 z-40 bg-white shadow-2xl"
    >
      <div className="h-full pt-11 flex flex-col justify-between">
        <div className="flex flex-col text-5xl gap-3 mt-0 px-10 md:px-24">
          <div className="text-black border-b border-black/30 uppercase text-sm mb-0">
            <p>Navigation</p>
          </div>
          <section className="bg-transparent mt-0">
            <div className="mx-auto max-w-7xl">
              {navItems.map((item, index) => {
                return (
                  <NavLink
                    key={item.href}
                    {...item}
                    setIsActive={setIsActive}
                    index={index + 1}
                  />
                );
              })}
            </div>
          </section>
        </div>
        {footer}
      </div>
      <Curve />
    </motion.div>
  );
};

export const Header: React.FC<iHeaderProps> = ({
  navItems = defaultNavItems,
  footer = <CustomFooter />,
}) => {
  const [isActive, setIsActive] = useState(false);
  const openAudioRef = useRef<HTMLAudioElement | null>(null);
  const closeAudioRef = useRef<HTMLAudioElement | null>(null);

  const handleClick = () => {
    if (isActive) {
      closeAudioRef.current?.play();
    } else {
      openAudioRef.current?.play();
    }
    setIsActive(!isActive);
  };

  return (
    <>
      <div className="relative">
        <div
          onClick={handleClick}
          aria-label={isActive ? "Close Navigation Menu" : "Open Navigation Menu"}
          className="fixed left-0 top-0 m-2 sm:m-3 z-50 w-12 h-12 rounded-none flex items-center justify-center cursor-pointer bg-white shadow-md border border-slate-200"
        >
          <div className="relative w-8 h-6 flex flex-col justify-between items-center">
            <span
              className={`block h-1 w-7 bg-black transition-transform duration-300 ${
                isActive ? "rotate-45 translate-y-2" : ""
              }`}
            ></span>
            <span
              className={`block h-1 w-7 bg-black transition-opacity duration-300 ${
                isActive ? "opacity-0" : ""
              }`}
            ></span>
            <span
              className={`block h-1 w-7 bg-black transition-transform duration-300 ${
                isActive ? "-rotate-45 -translate-y-3" : ""
              }`}
            ></span>
          </div>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {isActive && (
          <CurvedNavbar
            setIsActive={setIsActive}
            navItems={navItems}
            footer={footer}
          />
        )}
      </AnimatePresence>
    </>
  );
};

export default Header;
