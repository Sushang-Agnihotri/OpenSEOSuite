/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"], mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"] },
      colors: { brand: { 50: "#eef4ff", 100: "#dae6ff", 200: "#bdd2ff", 300: "#90b4ff", 400: "#5c8bfd", 500: "#3866f5", 600: "#2548e6", 700: "#1d37c9", 800: "#1e30a3", 900: "#1e2f80" } },
    },
  },
  plugins: [],
};
