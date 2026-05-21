import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        polymarket: {
          blue: "#0066FF",
          dark: "#0A0B0D",
          gray: "#1A1B1E",
          green: "#00C853",
          red: "#FF1744",
          yellow: "#FFD600",
        },
      },
    },
  },
  plugins: [],
};

export default config;
