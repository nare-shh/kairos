/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f4ff',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
        },
        surface: {
          900: '#0f0f13',
          800: '#16161d',
          700: '#1e1e28',
          600: '#262633',
        }
      },
      animation: {
        'price-flash': 'priceFlash 0.6s ease-in-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        priceFlash: {
          '0%':   { color: 'inherit' },
          '30%':  { color: '#22c55e', transform: 'scale(1.08)' },
          '100%': { color: 'inherit', transform: 'scale(1)' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        }
      }
    },
  },
  plugins: [],
}
