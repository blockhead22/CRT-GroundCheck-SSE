/*
 * Aether Docs — Shared JS
 * Cross-doc nav injection, auto-sidebar, theme toggle, scroll spy, prev/next pager.
 * Include before </body> in every doc.
 */
(function() {

  // ── Doc manifest (reading order) ──
  // Reading order deliberately separates the current product from the research
  // archive. A module appearing in the archive does not imply that it runs in
  // the current Workbench request path.
  var DOCS = [
    { href: 'home.html',                  label: 'Home',                   group: null },
    { href: 'start-here.html',            label: 'Start Here',             group: 'Current System' },
    { href: 'architecture.html',          label: 'Architecture Today',     group: 'Current System' },
    { href: 'system-status.html',         label: 'Status & Limits',         group: 'Current System' },
    { href: 'about.html',                 label: 'Names & Scope',           group: 'Current System' },
    { href: 'why-this-matters.html',      label: 'Why This Matters',       group: 'Research' },
    { href: 'experiments.html',           label: 'Evidence Overview',      group: 'Research' },
    { href: 'contradiction-density.html', label: 'Contradiction Density',  group: 'Research' },
    { href: 'sensitive-domains.html',     label: 'Sensitive Domains',      group: 'Research' },
    { href: 'continuity-blind.html',      label: 'Continuity-Blind',       group: 'Research' },
    { href: 'variance-probing.html',      label: 'Variance Probing',       group: 'Research' },
    { href: 'governance-validation.html', label: 'Governance Validation',  group: 'Research' },
    { href: 'bdg-reasoning-scaffolds.html', label: 'BRG Scaffolds',        group: 'Research' },
    { href: 'scaffolded_escape_research.html', label: 'Scaffolded Exploration', group: 'Research' },
    { href: 'labs.html',                  label: 'Lab Archive',            group: 'Research' },
    { href: 'meaning-compression-crt.html', label: 'Meaning Compression',  group: 'Theory & History' },
    { href: 'cascade-complexity.html',    label: 'Cascade Complexity',     group: 'Theory & History' },
    { href: 'belief-backprop.html',       label: 'Backward Influence',     group: 'Theory & History' },
    { href: 'epistemic-compression.html', label: 'Epistemic Compression',  group: 'Theory & History' },
    { href: 'geometric-memory.html',      label: 'Geometric Memory',       group: 'Theory & History' },
    { href: 'emotion-governance.html',    label: 'Emotion Governance',     group: 'Theory & History' },
    { href: 'structural-tension.html',    label: 'Structural Tension',     group: 'Theory & History' },
    { href: 'immune-agents.html',         label: 'Immune Agents',          group: 'Theory & History' },
    { href: 'whitepaper.html',            label: 'Evolved Thesis',         group: 'Theory & History' },
    { href: 'glossary.html',              label: 'Glossary',                group: 'Reference' },
    { href: 'claim-evaluation-guide.html', label: 'Claim Guide',           group: 'Reference' },
    { href: 'nick_paper.html',           label: 'Personal Narrative',       group: 'Reference' },
  ];

  var RESEARCH_PAGES = [
    'why-this-matters.html', 'experiments.html', 'contradiction-density.html',
    'sensitive-domains.html', 'continuity-blind.html', 'variance-probing.html',
    'governance-validation.html', 'bdg-reasoning-scaffolds.html',
    'scaffolded_escape_research.html', 'labs.html'
  ];
  var THEORY_PAGES = [
    'meaning-compression-crt.html', 'cascade-complexity.html',
    'belief-backprop.html', 'epistemic-compression.html', 'geometric-memory.html',
    'emotion-governance.html', 'structural-tension.html', 'immune-agents.html',
    'whitepaper.html', 'geometry.html', 'project_writeup.html',
    'WHY_CORE_IS_DIFFERENT_CODE_SNIPPETS.html'
  ];
  var DATED_RESULT_PAGES = ['governance-validation.html', 'claim-evaluation-guide.html'];

  // Detect subdirectory (labs/) and adjust prefix
  var inSubdir = window.location.pathname.replace(/\\/g, '/').includes('/labs/');
  var prefix = inSubdir ? '../' : '';
  var currentFile = window.location.pathname.replace(/\\/g, '/').split('/').pop() || 'index.html';
  // Cloudflare Pages serves clean URLs (no .html) — normalize to match manifest
  if (currentFile && !currentFile.includes('.')) {
    currentFile = currentFile + '.html';
  }
  if (currentFile === '' || currentFile === '.html' || window.location.pathname === '/') {
    currentFile = 'index.html';
  }

  // ── Inject cross-doc nav bar with dropdown groups ──
  function injectDocNav() {
    var nav = document.createElement('nav');
    nav.className = 'docnav';

    var home = document.createElement('a');
    home.className = 'docnav-home';
    home.href = prefix + 'home.html';
    home.textContent = 'Aeteros';
    nav.appendChild(home);

    // Build groups from manifest
    var groups = {};
    var groupOrder = [];
    DOCS.forEach(function(doc) {
      if (!doc.group) return;
      if (!groups[doc.group]) {
        groups[doc.group] = [];
        groupOrder.push(doc.group);
      }
      groups[doc.group].push(doc);
    });

    // Desktop: dropdown groups
    var groupsEl = document.createElement('div');
    groupsEl.className = 'docnav-groups';

    groupOrder.forEach(function(groupName) {
      var groupDiv = document.createElement('div');
      groupDiv.className = 'docnav-group';

      var label = document.createElement('div');
      label.className = 'docnav-group-label';
      label.innerHTML = groupName + ' <span class="docnav-group-arrow">&#9662;</span>';

      // Check if current page is in this group
      var hasActive = groups[groupName].some(function(d) { return d.href === currentFile; });
      if (hasActive) label.classList.add('has-active');

      groupDiv.appendChild(label);

      var dropdown = document.createElement('div');
      dropdown.className = 'docnav-dropdown';
      groups[groupName].forEach(function(doc) {
        var a = document.createElement('a');
        a.href = prefix + doc.href;
        a.textContent = doc.label;
        if (doc.href === currentFile) a.classList.add('docnav-active');
        dropdown.appendChild(a);
      });
      groupDiv.appendChild(dropdown);
      groupsEl.appendChild(groupDiv);
    });

    nav.appendChild(groupsEl);

    // Mobile: hamburger button
    var toggle = document.createElement('button');
    toggle.className = 'docnav-toggle';
    toggle.innerHTML = '&#9776;';
    toggle.setAttribute('aria-label', 'Toggle navigation');
    nav.appendChild(toggle);

    // Mobile: full-screen menu
    var mobileMenu = document.createElement('div');
    mobileMenu.className = 'docnav-mobile-menu';

    groupOrder.forEach(function(groupName) {
      var groupLabel = document.createElement('div');
      groupLabel.className = 'docnav-mobile-group-label';
      groupLabel.textContent = groupName;
      mobileMenu.appendChild(groupLabel);

      groups[groupName].forEach(function(doc) {
        var a = document.createElement('a');
        a.href = prefix + doc.href;
        a.textContent = doc.label;
        if (doc.href === currentFile) a.classList.add('docnav-active');
        mobileMenu.appendChild(a);
      });
    });

    // Theme toggle in mobile menu
    var mobileThemeBtn = document.createElement('button');
    mobileThemeBtn.className = 'docnav-mobile-theme';
    mobileThemeBtn.innerHTML = '&#9790; Toggle Theme';
    mobileThemeBtn.addEventListener('click', function() {
      var isLight = document.documentElement.getAttribute('data-theme') === 'light';
      var next = isLight ? 'dark' : 'light';
      localStorage.setItem('aether-theme', next);
      if (next === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        mobileThemeBtn.innerHTML = '&#9728; Toggle Theme';
      } else {
        document.documentElement.removeAttribute('data-theme');
        mobileThemeBtn.innerHTML = '&#9790; Toggle Theme';
      }
    });
    // Set initial icon
    if (document.documentElement.getAttribute('data-theme') === 'light') {
      mobileThemeBtn.innerHTML = '&#9728; Toggle Theme';
    }
    mobileMenu.appendChild(mobileThemeBtn);

    // Desktop dropdown click handlers
    var allGroups = groupsEl.querySelectorAll('.docnav-group');
    allGroups.forEach(function(grp) {
      var lbl = grp.querySelector('.docnav-group-label');
      var dd = grp.querySelector('.docnav-dropdown');
      lbl.addEventListener('click', function(e) {
        e.stopPropagation();
        var wasOpen = grp.classList.contains('open');
        // Close all
        allGroups.forEach(function(g) { g.classList.remove('open'); });
        // Toggle clicked and position dropdown
        if (!wasOpen) {
          grp.classList.add('open');
          var rect = lbl.getBoundingClientRect();
          dd.style.left = rect.left + 'px';
        }
      });
    });

    // Click outside closes dropdowns
    document.addEventListener('click', function() {
      allGroups.forEach(function(g) { g.classList.remove('open'); });
    });

    // Mobile toggle handler
    toggle.addEventListener('click', function(e) {
      e.stopPropagation();
      mobileMenu.classList.toggle('open');
      toggle.innerHTML = mobileMenu.classList.contains('open') ? '&#10005;' : '&#9776;';
    });

    // Insert nav at very top of body (outside page-layout to avoid hero stacking context)
    document.body.insertBefore(nav, document.body.firstChild);
    // Mobile menu right after nav
    nav.insertAdjacentElement('afterend', mobileMenu);
  }

  function injectDocumentStatus() {
    if (['home.html', 'start-here.html', 'architecture.html', 'system-status.html', 'about.html', 'index.html'].includes(currentFile)) return;

    var main = document.querySelector('main.main');
    if (!main) return;

    var kind = 'reference';
    var title = 'Reference document';
    var statusText = 'Use this page as background material. Current runtime behavior is documented under Current System.';

    if (RESEARCH_PAGES.includes(currentFile)) {
      kind = 'research';
      title = 'Repository-internal research';
      statusText = 'This page reports an experiment or research interpretation. It is not a statement that every described mechanism runs in the current Aether Workbench.';
    }
    if (THEORY_PAGES.includes(currentFile)) {
      kind = 'theory';
      title = 'Theory or historical architecture';
      statusText = 'This page preserves the project\'s research lineage. Concepts here may be experimental, unintegrated, superseded, or proposed; see Architecture Today for the live request path.';
    }
    if (DATED_RESULT_PAGES.includes(currentFile)) {
      kind = 'dated';
      title = 'Dated result snapshot';
      statusText = 'The measurements on this page are preserved as originally reported. They have not been silently recomputed for this documentation update. In particular, the published 47-case and 92-case contradiction counts came from different filtering or reclassification passes and must not be combined as one result.';
    }

    var banner = document.createElement('aside');
    banner.className = 'document-status document-status-' + kind;
    banner.setAttribute('aria-label', 'Document status');
    banner.innerHTML =
      '<div class="document-status-label">Document status</div>' +
      '<strong>' + title + '</strong>' +
      '<p>' + statusText + '</p>' +
      '<a href="' + prefix + 'architecture.html">Read the current architecture &rarr;</a>';
    main.insertBefore(banner, main.firstChild);
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

  // ── Inject changelog at bottom of main ──
  function injectChangelog() {
    var main = document.querySelector('main.main');
    if (!main) return;

    fetch(prefix + 'changelog.json')
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        if (!data) return;
        var entries = data[currentFile];
        if (!entries || !entries.length) return;

        var section = document.createElement('section');
        section.className = 'changelog-section';
        section.innerHTML =
          '<div class="accent-line"></div>' +
          '<h3 class="changelog-title">Change Log</h3>';

        var list = document.createElement('div');
        list.className = 'changelog-list';

        entries.forEach(function(e) {
          var row = document.createElement('div');
          row.className = 'changelog-entry';
          row.innerHTML =
            '<span class="changelog-date">' + e.date + '</span>' +
            '<span class="changelog-note">' + e.note + '</span>';
          list.appendChild(row);
        });

        section.appendChild(list);
        main.appendChild(section);
      })
      .catch(function() {}); // silent fail — changelog is optional
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

  // ── Inject standard footer (replaces any existing .footer div) ──
  function injectFooter() {
    if (document.body.classList.contains('aeteros-landing')) return;
    // Remove all existing footers
    var old = document.querySelectorAll('.footer');
    old.forEach(function(el) { el.remove(); });

    var footer = document.createElement('div');
    footer.className = 'footer';

    // Build link list from DOCS manifest
    var links = DOCS.filter(function(d) { return d.href !== currentFile; })
      .slice(0, 8)
      .map(function(d) { return '<a href="' + prefix + d.href + '">' + d.label + '</a>'; })
      .join(' &middot; ');

    footer.innerHTML = links + '<br><br>&copy; 2026 Aeteros Research';

    // Insert after .page-layout (not inside it — avoids grid issues)
    var pageLayout = document.querySelector('.page-layout');
    if (pageLayout && pageLayout.nextSibling) {
      pageLayout.parentNode.insertBefore(footer, pageLayout.nextSibling);
    } else if (pageLayout) {
      pageLayout.parentNode.appendChild(footer);
    } else {
      document.body.appendChild(footer);
    }
  }

  // ── Inject GSAP + ScrollTrigger ──
  function injectGSAP() {
    var scripts = [
      'https://cdn.jsdelivr.net/npm/gsap@3.12/dist/gsap.min.js',
      'https://cdn.jsdelivr.net/npm/gsap@3.12/dist/ScrollTrigger.min.js'
    ];
    var loaded = 0;
    window.__gsapCallbacks = window.__gsapCallbacks || [];

    function onLoad() {
      loaded++;
      if (loaded === scripts.length && window.gsap && window.ScrollTrigger) {
        gsap.registerPlugin(ScrollTrigger);
        document.body.classList.add('gsap-ready');
        // Fire any page-specific callbacks
        window.__gsapCallbacks.forEach(function(cb) { cb(); });
        window.__gsapCallbacks = [];
        // Load shared scroll animations
        var sa = document.createElement('script');
        sa.src = prefix + 'scroll-animations.js';
        document.body.appendChild(sa);
      }
    }

    scripts.forEach(function(src) {
      var s = document.createElement('script');
      s.src = src;
      s.crossOrigin = 'anonymous';
      s.onload = onLoad;
      s.onerror = function() { loaded++; }; // graceful degradation
      document.head.appendChild(s);
    });
  }

  injectBootstrap();
  injectGSAP();
  injectDocNav();
  injectDocumentStatus();
  injectPager();
  injectFooter();
  injectChangelog();
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
