import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        olive: {
          50: '#F3F5EA',
          100: '#E6EAD2',
          200: '#D2D9A8',
          300: '#BAC679',
          400: '#9AA94E',
          500: '#636B2F',
          600: '#525A27',
          700: '#42491F',
          800: '#323717',
          900: '#242711'
        },
        sand: {
          50: '#FBFAF7',
          100: '#F6F3EA',
          200: '#EEE8D6',
          300: '#E3D9B8'
        }
      },
      boxShadow: {
        soft: '0 8px 30px rgba(17, 24, 39, 0.10)',
        card: '0 10px 30px rgba(17, 24, 39, 0.08)'
      },
      borderRadius: {
        xl2: '1.25rem'
      }
    }
  },
  plugins: []
} satisfies Config
