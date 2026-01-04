module.exports = {
  content: ['./src/**/*.{js,jsx}', './public/**/*.html'],
  theme: {
    extend: {
      colors: {
        primary: '#10a37f',
        darkBg: '#0d0d0d',
        darkCard: '#1a1a1a',
        darkBorder: '#444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
