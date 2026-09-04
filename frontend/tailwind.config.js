/** @type {import('tailwindcss').Config} */

/**
 * ============================================================================
 *  COLOUR PALETTE — "Field Office" (humanised, draft 2)
 * ============================================================================
 * Draft 1 used the default cold blue/indigo/slate look that every generated
 * dashboard ships with. This palette is deliberately warmer and hand-picked
 * so the product reads like a real government field-office tool:
 *
 *   ink    — deep pine-charcoal. Sidebar, dark buttons, headings.
 *            (replaces the old `navy`)
 *   paper  — warm off-white / stone. Page background, borders, muted text.
 *            (replaces the cold `slate` greys)
 *   teal   — deep monsoon teal. Links, focus rings, primary accents.
 *   risk   — earth-pigment warning scale, borrowed from printed hazard maps:
 *            terracotta / turmeric / moss instead of pure red-amber-green.
 *
 * Every colour below is referenced by name in the components, so re-theming
 * the whole app later means editing THIS FILE ONLY.
 * ============================================================================
 */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Dark surfaces — sidebar, primary buttons, headings
        ink: {
          950: "#1d2723",
          900: "#26332e",
          800: "#33433c",
          700: "#45584f",
        },
        // Warm neutral scale — backgrounds, cards, borders, secondary text
        paper: {
          50: "#fbf9f5",
          100: "#f5f2ea",
          200: "#e9e4d8",
          300: "#d7d0be",
          400: "#b3ab99",
          500: "#8b8474",
          600: "#6b6459",
          700: "#4d4840",
        },
        // Accent — links, focus rings, chart bars
        teal: {
          50: "#e9f2f2",
          100: "#cfe3e4",
          500: "#1d7a86",
          600: "#15606b",
          700: "#0f4b54",
        },
        // Hazard scale — earth pigments, not screen primaries
        risk: {
          high: "#b4472f", // terracotta
          moderate: "#c8871d", // turmeric
          low: "#5b8c4f", // moss
          // soft tints for badges / icon chips
          highSoft: "#f8ebe6",
          moderateSoft: "#faf0dd",
          lowSoft: "#ecf2e8",
        },
      },
      fontFamily: {
        // Source Serif for headings gives the page a printed-document feel;
        // Inter stays for UI text because it is the most legible at 11-13px.
        sans: ["Inter", "system-ui", "sans-serif"],
        serif: ['"Source Serif 4"', "Georgia", "serif"],
      },
      keyframes: {
        // Used by the scrolling alert ticker (src/components/AlertTicker.jsx)
        marquee: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      animation: {
        marquee: "marquee 45s linear infinite",
      },
    },
  },
  plugins: [],
}
