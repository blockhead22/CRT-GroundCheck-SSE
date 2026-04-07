/*
 * Aether Docs — Shared JS
 * Auto-sidebar generation, theme toggle, scroll spy.
 * Include before </body> in every doc.
 */
(function() {
  var html = document.documentElement;

  // ── Auto-sidebar: generate links from <section> > h2 ──
  var sidebar = document.getElementById('docSidebar');
  if (sidebar && !sidebar.hasAttribute('data-manual-sidebar')) {
    var spacer = sidebar.querySelector('.sidebar-spacer');
    var sections = document.querySelectorAll('main.main > section[id]');
    // If sections lack IDs, try to assign from h2 text
    if (!sections.length) {
      sections = document.querySelectorAll('main.main > section');
      sections.forEach(function(sec) {
        if (!sec.id) {
          var h2 = sec.querySelector('h2');
          if (h2) {
            sec.id = h2.textContent.trim()
              .toLowerCase()
              .replace(/[^a-z0-9]+/g, '-')
              .replace(/^-|-$/g, '')
              .slice(0, 40);
          }
        }
      });
      // Re-select with IDs
      sections = document.querySelectorAll('main.main > section[id]');
    }
    var num = 1;
    sections.forEach(function(sec) {
      var h2 = sec.querySelector('h2');
      if (!h2) return;
      var a = document.createElement('a');
      a.href = '#' + sec.id;
      var label = h2.textContent.trim();
      // Truncate long titles
      if (label.length > 28) label = label.slice(0, 26) + '...';
      a.textContent = (num < 10 ? '0' : '') + num + ' ' + label;
      num++;
      if (spacer) {
        sidebar.insertBefore(a, spacer);
      } else {
        sidebar.appendChild(a);
      }
    });
  }

  // ── Theme toggle ──
  var btn = document.getElementById('themeToggle');
  var icon = document.getElementById('themeIcon');
  var label = document.getElementById('themeLabel');

  function applyTheme(theme) {
    if (theme === 'light') {
      html.setAttribute('data-theme', 'light');
      if (icon) icon.innerHTML = '&#9728;';
      if (label) label.textContent = 'Dark';
    } else {
      html.removeAttribute('data-theme');
      if (icon) icon.innerHTML = '&#9790;';
      if (label) label.textContent = 'Light';
    }
  }

  // Init: localStorage > system preference > dark default
  var stored = localStorage.getItem('aether-theme');
  if (stored) {
    applyTheme(stored);
  } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
    applyTheme('light');
  }

  if (btn) {
    btn.addEventListener('click', function() {
      var isLight = html.getAttribute('data-theme') === 'light';
      var next = isLight ? 'dark' : 'light';
      localStorage.setItem('aether-theme', next);
      applyTheme(next);
    });
  }

  // System preference listener
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function(e) {
      if (!localStorage.getItem('aether-theme')) {
        applyTheme(e.matches ? 'light' : 'dark');
      }
    });
  }

  // ── Scroll spy ──
  var links = sidebar ? sidebar.querySelectorAll('a[href^="#"]') : [];
  var spySections = [];
  links.forEach(function(a) {
    var id = a.getAttribute('href');
    if (id && id.startsWith('#')) {
      var el = document.getElementById(id.slice(1));
      if (el) spySections.push({ el: el, link: a });
    }
  });

  if (spySections.length) {
    function updateSpy() {
      var current = spySections[0];
      for (var i = 0; i < spySections.length; i++) {
        if (spySections[i].el.getBoundingClientRect().top <= 120) current = spySections[i];
      }
      links.forEach(function(a) { a.classList.remove('active'); });
      if (current) current.link.classList.add('active');
    }
    window.addEventListener('scroll', updateSpy);
    updateSpy();
  }
})();
