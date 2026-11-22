"use client";

import * as React from "react";
import type { SparklinePoint } from "@/hooks/use-live-data";
import { getHypeColor } from "@/lib/utils";

interface HypeSparklineProps {
  points?: SparklinePoint[];
  threshold?: number;
  height?: number;
  currentScore?: number;
}

export function HypeSparkline({
  points = [],
  threshold = 60,
  height = 56,
  currentScore = 0,
}: HypeSparklineProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [width, setWidth] = React.useState(260);

  React.useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setWidth(entry.contentRect.width);
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Prepare points (minimum 2 points for SVG line)
  const numScore = typeof currentScore === "number" && !isNaN(currentScore) ? currentScore : 0;
  const safePoints =
    Array.isArray(points) && points.length >= 2
      ? points
      : [
          { time: 1, score: numScore, mps: 0 },
          { time: 2, score: numScore, mps: 0 },
        ];

  // Scale Y: 0 to 100
  const maxY = 100;
  const paddingY = 4;
  const usableHeight = Math.max(height - paddingY * 2, 10);
  const safeWidth = Math.max(width || 260, 50);

  const getX = (index: number) => {
    const denom = Math.max(safePoints.length - 1, 1);
    const x = (index / denom) * safeWidth;
    return isNaN(x) ? 0 : Math.round(x * 10) / 10;
  };

  const getY = (val: number) => {
    const num = typeof val === "number" && !isNaN(val) ? val : 0;
    const clamped = Math.min(Math.max(num, 0), maxY);
    const y = height - paddingY - (clamped / maxY) * usableHeight;
    return isNaN(y) ? height / 2 : Math.round(y * 10) / 10;
  };

  // Generate path string
  const pathD = safePoints.reduce((acc, point, index) => {
    const x = getX(index);
    const y = getY(point?.score ?? 0);
    return index === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
  }, "");

  // Generate fill area path
  const areaD = `${pathD} L ${safeWidth} ${height} L 0 ${height} Z`;

  // Threshold Y coordinate
  const thresholdY = getY(threshold);

  const color = getHypeColor(numScore);
  const lastIndex = Math.max(safePoints.length - 1, 0);
  const lastX = getX(lastIndex);
  const lastY = getY(safePoints[lastIndex]?.score ?? 0);

  return (
    <div ref={containerRef} className="relative w-full overflow-hidden select-none" style={{ height }}>
      <svg
        width={width}
        height={height}
        className="overflow-visible block"
        viewBox={`0 0 ${width} ${height}`}
      >
        <defs>
          <linearGradient id={`grad-${currentScore}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={color.hex} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color.hex} stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Threshold dashed reference line */}
        <line
          x1={0}
          y1={thresholdY}
          x2={width}
          y2={thresholdY}
          stroke="#EF4444"
          strokeOpacity={0.4}
          strokeWidth={1}
          strokeDasharray="3 3"
        />

        {/* Filled Area */}
        <path d={areaD} fill={`url(#grad-${currentScore})`} />

        {/* Sparkline Stroke */}
        <path
          d={pathD}
          fill="none"
          stroke={color.hex}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Current Head Dot */}
        <circle cx={lastX} cy={lastY} r={3.5} fill={color.hex} className="transition-all" />
        {currentScore >= 60 && (
          <circle
            cx={lastX}
            cy={lastY}
            r={7}
            fill={color.hex}
            opacity={0.3}
            className="animate-ping"
          />
        )}
      </svg>

      {/* Threshold label tag */}
      <span
        className="absolute right-1 text-[9px] font-mono text-rose-500/70 select-none pointer-events-none"
        style={{ top: Math.max(thresholdY - 12, 0) }}
      >
        Trig {threshold}
      </span>
    </div>
  );
}
