module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        clay: "#eef3fb",
        ember: "#1b61c9",
        moss: "#14804a",
        mist: "#526277",
        sky: "#dfe9f7"
      },
      boxShadow: {
        card: "0 24px 60px rgba(15, 23, 42, 0.08), 0 6px 20px rgba(27, 97, 201, 0.08)"
      },
      backgroundImage: {
        mesh:
          "radial-gradient(circle at top left, rgba(27, 97, 201, 0.16), transparent 24%), radial-gradient(circle at top right, rgba(102, 126, 234, 0.10), transparent 26%), radial-gradient(circle at bottom right, rgba(20, 128, 74, 0.12), transparent 30%)"
      }
    }
  },
  daisyui: {
    themes: [
      {
        dealwatch: {
          primary: "#1b61c9",
          secondary: "#14804a",
          accent: "#7355ff",
          neutral: "#0f172a",
          "base-100": "#ffffff",
          "base-200": "#eef3fb",
          "base-300": "#dbe4f0",
          info: "#3b82f6",
          success: "#14804a",
          warning: "#c98612",
          error: "#dc2626"
        }
      }
    ]
  },
  plugins: [require("daisyui")]
};
