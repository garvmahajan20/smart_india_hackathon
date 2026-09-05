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
        containerType: "size",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundColor: "#EBF6F7",
          backgroundImage:
            "conic-gradient(from 90deg at 50% 50%, #EBF6F7 0%, #A2D7DD 33%, #00A3AF 67%, #274A78 100%)",
        }}
      />
    </div>
  );
}
