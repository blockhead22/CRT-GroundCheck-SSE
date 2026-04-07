/*
 * Aether Docs — Theme Toggle
 * Include before </body> in every doc page.
 * Injects a fixed toggle button and manages localStorage + system preference.
 */
(function() {
  var html = document.documentElement;

  // Inject toggle button
  var btn = document.createElement('button');
  btn.className = 'theme-toggle';
  btn.setAttribute('aria-label', 'Toggle light/dark theme');
  btn.innerHTML = '<span class="theme-toggle-icon" id="themeIcon">&#9790;</span><span id="themeLabel">Light</span>';
  document.body.appendChild(btn);

  var icon = btn.querySelector('#themeIcon');
  var label = btn.querySelector('#themeLabel');

  function applyTheme(theme) {
    if (theme === 'light') {
      html.setAttribute('data-theme', 'light');
      icon.innerHTML = '&#9728;';
      label.textContent = 'Dark';
    } else {
      html.removeAttribute('data-theme');
      icon.innerHTML = '&#9790;';
      label.textContent = 'Light';
    }
  }

  // Init: check localStorage, then system preference
  var stored = localStorage.getItem('aether-theme');
  if (stored) {
    applyTheme(stored);
  } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
    applyTheme('light');
  }

  btn.addEventListener('click', function() {
    var isLight = html.getAttribute('data-theme') === 'light';
    var next = isLight ? 'dark' : 'light';
    localStorage.setItem('aether-theme', next);
    applyTheme(next);
  });

  // Listen for system preference changes
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function(e) {
      if (!localStorage.getItem('aether-theme')) {
        applyTheme(e.matches ? 'light' : 'dark');
      }
    });
  }
})();
