/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#1c2421", soft: "#4a5652", faint: "#7a8682" },
        paper: { DEFAULT: "#f7f6f2", raised: "#ffffff", sunk: "#efede7" },
        line: "#dedbd2",
        brand: { 50: "#eef7f4", 100: "#d5ece5", 500: "#2f8a74", 600: "#1f6f5c", 700: "#185848", 800: "#123f34" },
        gap: { DEFAULT: "#b4541a", soft: "#fbeee4" },
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: { card: "0 1px 0 rgba(28,36,33,0.04), 0 1px 3px rgba(28,36,33,0.06)" },
    },
  },
  plugins: [],
};
