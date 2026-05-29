/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: { 0: '#0c0b09', 1: '#14110f', 2: '#1a1511', 3: '#1c1917' },
        border: { DEFAULT: 'rgba(245,158,11,0.10)', strong: 'rgba(245,158,11,0.20)' },
        content: { primary: '#f5f5f4', secondary: '#d6d3d1', muted: '#a8a29e' },
        accent: { DEFAULT: '#d97706', hover: '#b45309', soft: 'rgba(217,119,6,0.16)' },
        slate: {
          900: '#0f172a',
          800: '#1e293b',
          700: '#334155',
          600: '#475569',
          500: '#64748b',
          400: '#94a3b8',
          300: '#cbd5e1',
        },
        blue: {
          600: '#2563eb',
          700: '#1d4ed8',
        }
      },
      borderRadius: { card: '1rem' },
      boxShadow: { panel: '0 30px 100px rgba(8,7,5,0.55)' },
    },
  },
  plugins: [],
}