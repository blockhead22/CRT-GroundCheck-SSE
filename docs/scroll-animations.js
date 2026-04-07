/*
 * Aether Docs — Shared Scroll Animations (GSAP + ScrollTrigger)
 * Auto-discovers and animates sections, stat cards, tables, cards, pipelines.
 * Loaded by docs.js after GSAP is ready.
 */
(function() {
  if (!window.gsap || !window.ScrollTrigger) return;

  // Respect reduced motion preference
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var tl = gsap.timeline;

  // ── Helper: batch animate with ScrollTrigger ──
  function scrollReveal(selector, fromVars, stagger) {
    var els = document.querySelectorAll(selector);
    if (!els.length) return;
    gsap.set(els, { opacity: 0, y: fromVars.y || 30 });
    ScrollTrigger.batch(els, {
      onEnter: function(batch) {
        gsap.to(batch, {
          opacity: 1, y: 0,
          duration: fromVars.duration || 0.6,
          stagger: stagger || 0.08,
          ease: 'power2.out',
          overwrite: true
        });
      },
      start: 'top 88%'
    });
  }

  // ── Sections: fade up ──
  scrollReveal('main.main > section', { y: 40, duration: 0.7 }, 0);

  // ── Stat cards: fade up + stagger ──
  scrollReveal('.stat-row > .stat-card, .stat-row > .stat-cell', { y: 25, duration: 0.5 }, 0.1);

  // ── Cards: fade up + stagger ──
  scrollReveal([
    '.law-block', '.principle', '.agent-cell', '.pipeline-layer',
    '.immune-card', '.regime-card', '.method-card', '.phase-card',
    '.glossary-entry', '.paper-card', '.guide-card', '.claim-card',
    '.step-card', '.status-card', '.rubric-card', '.gap-card',
    '.area-card', '.direction-card', '.signal-card', '.domain-card',
    '.ext-cite', '.sub-claim', '.contra-pair', '.audit-pair',
    '.log-card'
  ].join(', '), { y: 20, duration: 0.5 }, 0.06);

  // ── Tables: fade in ──
  scrollReveal('table, .table-responsive', { y: 15, duration: 0.5 }, 0);

  // ── Quote blocks: slide from left ──
  var quotes = document.querySelectorAll('.quote-block, .quote, .remark, .impl-block, .caution-block, .harm-box');
  if (quotes.length) {
    gsap.set(quotes, { opacity: 0, x: -20 });
    ScrollTrigger.batch(quotes, {
      onEnter: function(batch) {
        gsap.to(batch, {
          opacity: 1, x: 0,
          duration: 0.6,
          stagger: 0.05,
          ease: 'power2.out',
          overwrite: true
        });
      },
      start: 'top 85%'
    });
  }

  // ── Pipeline rows: sequential cascade ──
  var pipelineRows = document.querySelectorAll('.pipeline .pipeline-row, .pipeline-stack .pipeline-layer');
  if (pipelineRows.length) {
    gsap.set(pipelineRows, { opacity: 0, x: -15 });
    ScrollTrigger.batch(pipelineRows, {
      onEnter: function(batch) {
        gsap.to(batch, {
          opacity: 1, x: 0,
          duration: 0.4,
          stagger: 0.12,
          ease: 'power2.out',
          overwrite: true
        });
      },
      start: 'top 85%'
    });
  }

  // ── Stat value counter animation ──
  var statValues = document.querySelectorAll('.stat-value');
  statValues.forEach(function(el) {
    var text = el.textContent.trim();
    // Only animate numeric values
    var match = text.match(/^([\d,.]+)(%?)(\+?)$/);
    if (!match) return;
    var target = parseFloat(match[1].replace(/,/g, ''));
    var suffix = match[2] + match[3];
    var hasComma = match[1].indexOf(',') !== -1;
    var decimals = match[1].indexOf('.') !== -1 ? match[1].split('.')[1].length : 0;

    el.textContent = '0' + suffix;
    ScrollTrigger.create({
      trigger: el,
      start: 'top 90%',
      once: true,
      onEnter: function() {
        gsap.to({ val: 0 }, {
          val: target,
          duration: 1.2,
          ease: 'power2.out',
          onUpdate: function() {
            var v = this.targets()[0].val;
            if (decimals > 0) {
              v = v.toFixed(decimals);
            } else {
              v = Math.round(v);
            }
            if (hasComma) {
              v = v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
            }
            el.textContent = v + suffix;
          }
        });
      }
    });
  });

  // ── Hero entrance: fade in the hero-inner content ──
  var heroInner = document.querySelector('.hero-inner');
  if (heroInner) {
    var heroEls = heroInner.children;
    gsap.set(heroEls, { opacity: 0, y: 30 });
    gsap.to(heroEls, {
      opacity: 1, y: 0,
      duration: 0.8,
      stagger: 0.15,
      ease: 'power3.out',
      delay: 0.2
    });
  }

  // ── Scroll cue: gentle bounce ──
  var cue = document.querySelector('.scroll-cue');
  if (cue) {
    gsap.to(cue, {
      y: 8,
      duration: 1.5,
      ease: 'sine.inOut',
      yoyo: true,
      repeat: -1
    });
    // Fade out on scroll
    ScrollTrigger.create({
      trigger: 'main.main',
      start: 'top 80%',
      onEnter: function() { gsap.to(cue, { opacity: 0, duration: 0.3 }); },
      onLeaveBack: function() { gsap.to(cue, { opacity: 0.7, duration: 0.3 }); }
    });
  }

  // ── Accent lines: grow from left ──
  var accents = document.querySelectorAll('.accent-line');
  if (accents.length) {
    gsap.set(accents, { scaleX: 0, transformOrigin: 'left center' });
    ScrollTrigger.batch(accents, {
      onEnter: function(batch) {
        gsap.to(batch, { scaleX: 1, duration: 0.6, ease: 'power2.out', overwrite: true });
      },
      start: 'top 90%'
    });
  }

})();
