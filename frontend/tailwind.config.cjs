module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14213d",
        clay: "#f5efe4",
        ember: "#b84c27",
        moss: "#4e6e58"
      },
      boxShadow: {
        card: "0 18px 60px rgba(20, 33, 61, 0.12)"
      },
      backgroundImage: {
        mesh:
          "radial-gradient(circle at top left, rgba(184, 76, 39, 0.18), transparent 28%), radial-gradient(circle at bottom right, rgba(78, 110, 88, 0.22), transparent 34%)"
      }
    }
  },
  daisyui: {
    themes: [
      {
        dealwatch: {
          primary: "#14213d",
          secondary: "#4e6e58",
          accent: "#b84c27",
          neutral: "#2c2d31",
          "base-100": "#fcfaf5",
          "base-200": "#f5efe4",
          "base-300": "#e5dccd",
          info: "#3b82f6",
          success: "#1f9d55",
          warning: "#d97706",
          error: "#dc2626"
        }
      }
    ]
  },
  plugins: [require("daisyui")]
};
