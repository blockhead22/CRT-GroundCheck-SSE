"""
Migrate 15 doc pages to the unified Aether design system.
- Wraps content in .page-layout grid with sidebar
- Adds base.css import
- Strips shared boilerplate CSS from inline <style>
- Replaces theme.js with docs.js
- Converts .container to .main
"""
import re
from pathlib import Path

DOCS_DIR = Path(__file__).parent

FILES = [
    "architecture.html", "whitepaper.html", "cascade-complexity.html",
    "emotion-governance.html", "contradiction-density.html",
    "geometric-memory.html", "variance-probing.html", "immune-agents.html",
    "experiments.html", "continuity-blind.html", "glossary.html",
    "throughline.html", "cascade-viz.html", "variance-landscape.html",
    "project_writeup.html",
]

# CSS rules to strip from inline <style> blocks (these are now in base.css)
STRIP_PATTERNS = [
    # Body
    r'\s*body\s*\{[^}]*\}\s*',
    # Hero section (entire block including sub-rules)
    r'\s*/\*\s*=+\s*HERO\s*=+\s*\*/.*?(?=\s*/\*\s*=+\s*(?:LAYOUT|CONTAINER)|(?:\s*\.container\s*\{))',
    # Container rule
    r'\s*\.container\s*\{[^}]*\}\s*',
    # Section rule
    r'\s*section\s*\{[^}]*\}\s*',
    # Base typography (h2, h3, h4, p, strong, em, a, ul, ol, li — only the bare selectors)
    r'\s*h2\s*\{[^}]*\}\s*',
    r'\s*h3\s*\{[^}]*\}\s*',
    r'\s*h4\s*\{[^}]*\}\s*',
    r'\s*p\s*\{[^}]*\}\s*',
    r'\s*strong\s*\{[^}]*\}\s*',
    r'\s*em\s*\{[^}]*\}\s*',
    r'\s*a\s*\{[^}]*\}\s*',
    r'\s*a:hover\s*\{[^}]*\}\s*',
    r'\s*ul\s*,\s*ol\s*\{[^}]*\}\s*',
    r'\s*li\s*\{[^}]*\}\s*',
    # Stat cards
    r'\s*\.stat-row\s*\{[^}]*\}\s*',
    r'\s*\.stat-card\s*\{[^}]*\}\s*',
    r'\s*\.stat-value\s*\{[^}]*\}\s*',
    r'\s*\.stat-value\.[a-z]+\s*\{[^}]*\}\s*',
    r'\s*\.stat-label\s*\{[^}]*\}\s*',
    # Tables
    r'\s*\.table-wrap\s*\{[^}]*\}\s*',
    r'\s*table\s*\{[^}]*\}\s*',
    r'\s*thead\s+th\s*\{[^}]*\}\s*',
    r'\s*tbody\s+td\s*\{[^}]*\}\s*',
    r'\s*tbody\s+tr:last-child\s+td\s*\{[^}]*\}\s*',
    r'\s*tbody\s+tr:hover\s*\{[^}]*\}\s*',
    r'\s*td\s+strong\s*\{[^}]*\}\s*',
    r'\s*td\s+code\s*\{[^}]*\}\s*',
    # Section number
    r'\s*\.section-number\s*\{[^}]*\}\s*',
    # Accent line
    r'\s*\.accent-line\s*\{[^}]*\}\s*',
    # Footer
    r'\s*\.footer\s*\{[^}]*\}\s*',
    r'\s*\.footer\s+a\s*\{[^}]*\}\s*',
    # Quote block
    r'\s*\.quote-block\s*\{[^}]*\}\s*',
    r'\s*\.quote-block\s+p\s*\{[^}]*\}\s*',
    # Badge basics
    r'\s*\.badge\s*\{[^}]*\}\s*',
    r'\s*\.badge-proven\s*\{[^}]*\}\s*',
    r'\s*\.badge-active\s*\{[^}]*\}\s*',
    r'\s*\.badge-concept\s*\{[^}]*\}\s*',
    r'\s*\.badge-built\s*\{[^}]*\}\s*',
    r'\s*\.badge-planned\s*\{[^}]*\}\s*',
    r'\s*\.badge-progress\s*\{[^}]*\}\s*',
    r'\s*\.badge-conjecture\s*\{[^}]*\}\s*',
    r'\s*\.badge-def\s*\{[^}]*\}\s*',
    r'\s*\.badge-prop\s*\{[^}]*\}\s*',
    r'\s*\.badge-corollary\s*\{[^}]*\}\s*',
    # Link button
    r'\s*\.link-btn\s*\{[^}]*\}\s*',
    r'\s*\.link-btn:hover\s*\{[^}]*\}\s*',
    # Note
    r'\s*\.note\s*\{[^}]*\}\s*',
    # Code (bare selector)
    r'\s*code\s*\{[^}]*\}\s*',
    # Reset
    r'\s*\*\s*\{[^}]*\}\s*',
    # Scroll cue (part of hero)
    r'\s*\.scroll-cue\s*\{[^}]*\}\s*',
    # Keyframes
    r'\s*@keyframes\s+drift\s*\{[^}]*\}\s*',
    r'\s*@keyframes\s+pulse\s*\{[^}]*\}\s*',
]


def extract_title_from_hero(html_content):
    """Extract a short sidebar title from the hero badge or h1."""
    m = re.search(r'class="hero-badge"[^>]*>([^<]+)<', html_content)
    if m:
        text = m.group(1).strip()
        # Clean up entities and trim
        text = text.replace('&mdash;', '-').replace('&amp;', '&').replace('·', '-')
        # Take first part before dash
        parts = re.split(r'\s*[-]\s*', text)
        return parts[0].strip()[:30]
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.DOTALL)
    if m:
        text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        return text[:30]
    return "Aether Docs"


def strip_boilerplate_css(style_content):
    """Remove shared CSS rules that are now in base.css."""
    result = style_content

    # Strip hero section block (greedy match from HERO comment to LAYOUT/CONTAINER comment)
    result = re.sub(
        r'/\*\s*=+\s*HERO\s*=+\s*\*/.*?(?=/\*\s*=+\s*(?:LAYOUT|CONTAINER))',
        '', result, flags=re.DOTALL
    )

    # Strip individual patterns
    for pattern in STRIP_PATTERNS:
        result = re.sub(pattern, '\n', result, flags=re.DOTALL)

    # Strip responsive block that only contains shared rules
    # (keep if it has page-specific rules)
    result = re.sub(
        r'@media\s*\(max-width:\s*(?:700|900)px\)\s*\{[^}]*\.container\s*\{[^}]*\}[^}]*\}',
        '', result, flags=re.DOTALL
    )

    # Clean up excessive blank lines
    result = re.sub(r'\n{4,}', '\n\n', result)

    return result.strip()


def migrate_file(filepath):
    """Migrate a single doc to the new design system."""
    content = filepath.read_text(encoding='utf-8')
    original = content

    # 1. Add base.css link after </style> (before theme.css if present)
    if 'base.css' not in content:
        content = content.replace(
            '</style>\n<link rel="stylesheet" href="theme.css">',
            '</style>\n<link rel="stylesheet" href="base.css">\n<link rel="stylesheet" href="theme.css">'
        )
        # If theme.css wasn't on the next line, try just after </style>
        if 'base.css' not in content:
            content = content.replace(
                '</style>',
                '</style>\n<link rel="stylesheet" href="base.css">\n<link rel="stylesheet" href="theme.css">'
            )

    # 2. Replace theme.js with docs.js
    content = content.replace('theme.js', 'docs.js')

    # 3. Strip shared boilerplate from inline <style>
    style_match = re.search(r'(<style>)(.*?)(</style>)', content, re.DOTALL)
    if style_match:
        stripped = strip_boilerplate_css(style_match.group(2))
        # Also strip MathJax config that might be before the style
        if stripped.strip():
            content = content[:style_match.start()] + '<style>\n' + stripped + '\n</style>' + content[style_match.end():]
        else:
            # If ALL CSS was shared, remove the style block entirely
            content = content[:style_match.start()] + content[style_match.end():]

    # 4. Wrap body content in .page-layout grid with sidebar
    title = extract_title_from_hero(content)

    sidebar_html = f'''<nav class="sidebar" id="docSidebar">
  <div class="sidebar-title">{title}</div>
  <div class="sidebar-spacer"></div>
  <button class="theme-toggle" id="themeToggle" aria-label="Toggle light/dark theme">
    <span class="theme-toggle-icon" id="themeIcon">&#9790;</span>
    <span id="themeLabel">Light</span>
  </button>
  <div class="sidebar-footer">2026 Aeteros Research</div>
</nav>'''

    # Find the hero div and container div
    # Pattern: after </head><body>, we have hero then container
    # Transform: wrap in .page-layout, add sidebar, convert container to main

    # Insert page-layout opening after <body>
    if '<div class="page-layout">' not in content:
        content = content.replace('<body>\n', '<body>\n<div class="page-layout">\n')
        content = content.replace('<body>', '<body>\n<div class="page-layout">')

        # Add sidebar after hero closing div (find the scroll-cue then its parent div close)
        # The hero close is the </div> after scroll-cue
        hero_end = re.search(r'(</div>\s*<!-- scroll-cue -->|<div class="scroll-cue">[^<]*</div>\s*</div>)', content)
        if not hero_end:
            # Try finding the hero closing more generically
            hero_end = re.search(r'(class="scroll-cue"[^>]*>[^<]*</div>\s*</div>)', content)
        if not hero_end:
            # Last resort: find </div> after "SCROLL" text
            matches = list(re.finditer(r'SCROLL[^<]*</div>\s*</div>', content))
            if matches:
                pos = matches[0].end()
                content = content[:pos] + '\n\n' + sidebar_html + '\n' + content[pos:]

        if hero_end and sidebar_html not in content:
            pos = hero_end.end()
            content = content[:pos] + '\n\n' + sidebar_html + '\n' + content[pos:]

        # Convert <div class="container"> to <main class="main">
        content = content.replace('<div class="container">', '<main class="main">')
        # Find and replace the matching closing </div> before footer or </body>
        # The container's closing </div> is typically before the footer
        content = re.sub(
            r'(</main>|<div class="footer">)',
            r'\1',
            content
        )
        # Replace the last </div> before footer with </main>
        # Actually we need to close the container-turned-main
        # The container div should have a closing </div> that we need to change to </main>
        # Find the footer and ensure </main> is before it
        if '<div class="footer">' in content:
            content = content.replace(
                '<div class="footer">',
                '</main>\n<div class="footer">'
            )
            # But we might have doubled up - clean
            content = content.replace('</main>\n</main>', '</main>')

        # Close page-layout before </body>
        content = content.replace(
            '<script src="docs.js"></script>\n</body>',
            '</div>\n<script src="docs.js"></script>\n</body>'
        )

    filepath.write_text(content, encoding='utf-8')
    changed = content != original
    return changed


def main():
    for fname in FILES:
        fpath = DOCS_DIR / fname
        if not fpath.exists():
            print(f"  SKIP (not found): {fname}")
            continue
        changed = migrate_file(fpath)
        print(f"  {'MIGRATED' if changed else 'NO CHANGE'}: {fname}")


if __name__ == '__main__':
    main()
