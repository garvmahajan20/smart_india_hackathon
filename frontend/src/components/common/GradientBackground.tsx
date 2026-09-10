import React from "react";

export function GradientBackground({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={className}
      style={{
        position: "relative",
        overflow: "hidden",
        width: "100%",
        height: "100%",
        backgroundColor: "#f4f8fb",
        backgroundImage:
          "radial-gradient(circle at 12% 8%, rgba(37,99,235,0.10), transparent 30%), radial-gradient(circle at 88% 14%, rgba(14,165,233,0.09), transparent 28%), radial-gradient(circle at 72% 92%, rgba(15,118,110,0.08), transparent 32%), linear-gradient(135deg, #f8fbfd 0%, #eef5f8 48%, #f7fafc 100%)",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "linear-gradient(rgba(15,23,42,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(15,23,42,0.025) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
          maskImage: "linear-gradient(to bottom, rgba(0,0,0,0.45), transparent 72%)",
          WebkitMaskImage: "linear-gradient(to bottom, rgba(0,0,0,0.45), transparent 72%)",
        }}
      />
    </div>
  );
}
