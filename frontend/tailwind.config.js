/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0D12",
        surface: "#12161D",
        surface2: "#171C24",
        border: "#232935",
        text: "#E6E9EE",
        "text-dim": "#8B93A1",
        "text-faint": "#5B6270",
        long: "#3DD68C",
        short: "#F0596B",
        watch: "#E8B339",
        accent: "#4C8DFF",
      },
      fontFamily: {
        mono: ["SF Mono", "Consolas", "Menlo", "Liberation Mono", "monospace"],
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "Inter", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};
