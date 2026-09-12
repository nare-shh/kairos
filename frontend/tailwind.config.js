/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Editorial paper palette: warm off-white surfaces, near-black ink,
        // sage green for actions, clay for imagery.
        paper: { 50: '#FDFCFA', 100: '#F7F5F0', 200: '#F0EDE5', 300: '#E7E2D7' },
        line:  { DEFAULT: '#DFD9CC', strong: '#CDC5B4' },
        ink:   { DEFAULT: '#16170F', 700: '#34352C', 500: '#6E6F63', 400: '#94958A' },
        sage:  { 100: '#E6EBDD', 300: '#BCC7A6', 500: '#7E8F62', 600: '#647550', 700: '#4A5839', 900: '#212A18' },
        clay:  { 100: '#EFE4D5', 300: '#DCC6AC', 500: '#96683A' },
        // Price and stock signals
        flag:  { up: '#9B3B2F', down: '#647550', warn: '#9A6318' },
      },
      fontFamily: {
        display: ['"Instrument Serif"', 'Georgia', 'Cambria', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
      letterSpacing: {
        caps: '0.14em',
      },
      animation: {
        'price-flash': 'priceFlash 0.8s ease-in-out',
        'slide-up': 'slideUp 0.35s ease-out',
      },
      keyframes: {
        priceFlash: {
          '0%':   { color: 'inherit' },
          '30%':  { color: '#647550', transform: 'scale(1.04)' },
          '100%': { color: 'inherit', transform: 'scale(1)' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
