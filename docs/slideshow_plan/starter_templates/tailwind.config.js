/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/templates/**/*.html',
    './app/blueprints/**/*.py',   // for any HTML strings in Python
  ],
  darkMode: 'class',
  theme: {
    // Mobile-first breakpoints
    screens: {
      'sm': '640px',
      'md': '768px',
      'lg': '1024px',
      'xl': '1280px',
      '2xl': '1536px',
    },
    extend: {
      colors: {
        ink: {
          DEFAULT: '#1A1F36',
          soft:    '#4A5170',
          faint:   '#8A90A8',
        },
        paper: {
          DEFAULT: '#FBF9F4',
          raised:  '#FFFFFF',
        },
        line: {
          DEFAULT: '#E8E4DA',
          soft:    '#F1EEE6',
        },
        indigo: {
          DEFAULT: '#2E3271',
          deep:    '#1F225A',
          soft:    '#EEF0FA',
        },
        turmeric: {
          DEFAULT: '#E5A63E',
          soft:    '#FAF0DA',
        },
        success: {
          DEFAULT: '#2F7D4F',
          soft:    '#E4F3EA',
        },
        danger: {
          DEFAULT: '#B23A48',
          soft:    '#F7E4E7',
        },
        caution: {
          DEFAULT: '#B4761F',
          soft:    '#FAF0DA',
        },
      },
      fontFamily: {
        sans: [
          '"Inter Tight"',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
        mono: [
          '"JetBrains Mono"',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'monospace',
        ],
      },
      fontSize: {
        // Custom type scale
        'display':  ['2rem',    { lineHeight: '2.5rem',  fontWeight: '700' }],
        'h1':       ['1.5rem',  { lineHeight: '2rem',    fontWeight: '700' }],
        'h2':       ['1.25rem', { lineHeight: '1.75rem', fontWeight: '600' }],
        'h3':       ['1.0625rem', { lineHeight: '1.5rem', fontWeight: '600' }],
        'body':     ['1rem',    { lineHeight: '1.5rem',  fontWeight: '400' }],
        'small':    ['0.875rem', { lineHeight: '1.25rem', fontWeight: '400' }],
        'caption':  ['0.75rem', { lineHeight: '1rem',    fontWeight: '400' }],
        'micro':    ['0.6875rem', { lineHeight: '0.875rem', fontWeight: '500', letterSpacing: '0.02em' }],
      },
      borderRadius: {
        'tight':       '4px',
        'standard':    '8px',
        'comfortable': '12px',
      },
      boxShadow: {
        'raise': '0 1px 2px rgba(26,31,54,0.06), 0 4px 12px rgba(26,31,54,0.04)',
        'lift':  '0 4px 8px rgba(26,31,54,0.08), 0 16px 32px rgba(26,31,54,0.10)',
      },
      spacing: {
        'safe-top':    'env(safe-area-inset-top)',
        'safe-bottom': 'env(safe-area-inset-bottom)',
      },
      transitionDuration: {
        'quick':       '120ms',
        'standard':    '200ms',
        'comfortable': '320ms',
        'slow':        '500ms',
      },
      transitionTimingFunction: {
        'standard':    'cubic-bezier(0.4, 0, 0.2, 1)',
        'emphasized':  'cubic-bezier(0.32, 0.72, 0, 1)',
      },
      minHeight: {
        'screen-dvh': '100dvh',
      },
    },
  },
  plugins: [],
};
