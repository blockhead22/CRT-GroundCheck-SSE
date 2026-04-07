/*
 * Aether Docs — Shared JS
 * Cross-doc nav injection, auto-sidebar, theme toggle, scroll spy, prev/next pager.
 * Include before </body> in every doc.
 */
(function() {

  // ── Doc manifest (reading order) ──
  var DOCS = [
    { href: 'index.html',                label: 'Home',                 group: null },
    { href: 'contradiction-density.html',label: 'Contradiction Density',group: 'Research' },
    { href: 'continuity-blind.html',     label: 'Continuity Blind',     group: 'Research' },
    { href: 'sensitive-domains.html',    label: 'Sensitive Domains',    group: 'Research' },
    { href: 'whitepaper.html',           label: 'Whitepaper',           group: 'Research' },
    { href: 'immune-agents.html',        label: 'Immune Agents',        group: 'Research' },
    { href: 'experiments.html',          label: 'Experiments',          group: 'Research' },
    { href: 'architecture.html',         label: 'Architecture',         group: 'Theory' },
    { href: 'cascade-complexity.html',   label: 'Cascade Complexity',   group: 'Theory' },
    { href: 'geometric-memory.html',     label: 'Geometric Memory',     group: 'Theory' },
    { href: 'variance-probing.html',     label: 'Variance Probing',     group: 'Theory' },
    { href: 'variance-landscape.html',   label: 'Variance Landscape',   group: 'Theory' },
    { href: 'emotion-governance.html',   label: 'Emotion Governance',   group: 'Theory' },
    { href: 'throughline.html',          label: 'Throughline',          group: 'Reference' },
    { href: 'glossary.html',             label: 'Glossary',             group: 'Reference' },
    { href: 'claim-evaluation-guide.html',label: 'Claim Eval Guide',   group: 'Reference' },
  ];

  // Detect subdirectory (labs/) and adjust prefix
  var inSubdir = window.location.pathname.replace(/\\/g, '/').includes('/labs/');
  var prefix = inSubdir ? '../' : '';
  var currentFile = window.location.pathname.replace(/\\/g, '/').split('/').pop() || 'index.html';

  // ── Inject cross-doc nav bar ──
  function injectDocNav() {
    var nav = document.createElement('nav');
    nav.className = 'docnav';

    var home = document.createElement('a');
    home.className = 'docnav-home';
    home.href = prefix + 'index.html';
    home.textContent = 'Aeteros';
    nav.appendChild(home);

    var links = document.createElement('div');
    links.className = 'docnav-links';

    var lastGroup = null;
    DOCS.forEach(function(doc) {
      if (doc.href === 'index.html') return; // home already shown
      if (doc.group !== lastGroup && lastGroup !== null) {
        var sep = document.createElement('div');
        sep.className = 'docnav-sep';
        links.appendChild(sep);
      }
      lastGroup = doc.group;
      var a = document.createElement('a');
      a.href = prefix + doc.href;
      a.textContent = doc.label;
      if (doc.href === currentFile) a.classList.add('docnav-active');
      links.appendChild(a);
    });

    nav.appendChild(links);
    document.body.insertBefore(nav, document.body.firstChild);
  }

  // ── Inject prev/next pager into main ──
  function injectPager() {
    var main = document.querySelector('main.main');
    if (!main) return;
    // Only for docs in the manifest
    var idx = DOCS.findIndex(function(d) { return d.href === currentFile; });
    if (idx === -1) return;
    var prev = idx > 0 ? DOCS[idx - 1] : null;
    var next = idx < DOCS.length - 1 ? DOCS[idx + 1] : null;
    if (!prev && !next) return;

    var pager = document.createElement('div');
    pager.className = 'doc-pager';

    if (prev) {
      var pa = document.createElement('a');
      pa.href = prefix + prev.href;
      pa.innerHTML =
        '<span class="doc-pager-dir">&larr; Previous</span>' +
        '<span class="doc-pager-title">' + prev.label + '</span>';
      pager.appendChild(pa);
    } else {
      pager.appendChild(document.createElement('span')); // spacer
    }

    if (next) {
      var na = document.createElement('a');
      na.href = prefix + next.href;
      na.className = 'doc-pager-next';
      na.innerHTML =
        '<span class="doc-pager-dir">Next &rarr;</span>' +
        '<span class="doc-pager-title">' + next.label + '</span>';
      pager.appendChild(na);
    }

    main.appendChild(pager);
  }

  // ── Inject Bootstrap 5 CSS (before first paint where possible) ──
  function injectBootstrap() {
    var bs = document.createElement('link');
    bs.rel = 'stylesheet';
    bs.href = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css';
    bs.crossOrigin = 'anonymous';
    // Insert BEFORE base.css so our styles override Bootstrap
    var firstCSS = document.querySelector('link[rel="stylesheet"]');
    if (firstCSS) {
      firstCSS.parentNode.insertBefore(bs, firstCSS);
    } else {
      document.head.appendChild(bs);
    }
  }

  // ── Apply Bootstrap utility classes to existing elements ──
  function bootstrapify() {
    // Make all tables responsive
    var tables = document.querySelectorAll('table');
    tables.forEach(function(t) {
      // Skip if already wrapped in a responsive container
      if (t.parentNode.classList.contains('table-responsive') || t.parentNode.classList.contains('table-wrap') || t.parentNode.classList.contains('metric-table-wrap')) return;
      var wrap = document.createElement('div');
      wrap.className = 'table-responsive';
      t.parentNode.insertBefore(wrap, t);
      wrap.appendChild(t);
    });

    // Add Bootstrap table class
    tables.forEach(function(t) {
      t.classList.add('table', 'table-sm');
    });

    // Make images responsive
    var imgs = document.querySelectorAll('img');
    imgs.forEach(function(img) {
      img.classList.add('img-fluid');
    });

    // Add container-fluid to main if not present
    var main = document.querySelector('main.main');
    if (main && !main.classList.contains('container-fluid')) {
      main.style.maxWidth = '100%';
      main.style.overflowX = 'hidden';
    }
  }

  injectBootstrap();
  injectDocNav();
  injectPager();
  // Run bootstrapify after DOM is settled
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapify);
  } else {
    bootstrapify();
  }
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
