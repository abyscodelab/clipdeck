import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0D0D0D',
        surface: {
          DEFAULT: '#161616',
          hover: '#1E1E1E',
          raised: '#222222',
        },
        border: 'rgba(255, 255, 255, 0.08)',
        'border-strong': 'rgba(255, 255, 255, 0.14)',
        accent: {
          DEFAULT: '#E8E8E8',
          hover: '#FFFFFF',
          muted: 'rgba(255, 255, 255, 0.06)',
        },
        brand: {
          DEFAULT: '#10B981',   /* emerald — the "live" and primary action color */
          hover: '#34D399',
        },
        live: '#10B981',
        hype: {
          low: '#10B981',
          medium: '#F59E0B',
          high: '#EF4444',
        },
        danger: '#DC2626',
        warning: '#F59E0B',
        success: '#10B981',
        muted: '#737373',
        card: {
          DEFAULT: '#161616',
          foreground: '#E8E8E8',
        },
      },
      borderRadius: {
        '2xl': '16px',
        'xl': '12px',
        'lg': '10px',
        'md': '8px',
        'sm': '6px',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'border': '0 0 0 1px rgba(255, 255, 255, 0.06)',
        'border-hover': '0 0 0 1px rgba(255, 255, 255, 0.12)',
        'elevated': '0 0 0 1px rgba(255, 255, 255, 0.06), 0 4px 16px rgba(0, 0, 0, 0.4)',
        'float': '0 8px 32px rgba(0, 0, 0, 0.5)',
      },
    },
  },
  plugins: [],
};

export default config;
