---
name: frontend-design
enabled: false
version: "1.0"
description: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, or applications. Generates creative, polished code that avoids generic AI aesthetics.
license: Complete terms in LICENSE.txt
web_tier: 1
---

This skill guides creation of distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics. Implement real working code with exceptional attention to aesthetic details and creative choices.

The user provides frontend requirements: a component, page, application, or interface to build. They may include context about the purpose, audience, or technical constraints.

## Brand Foundation

**Default to the Lumif.ai design system** for all outputs unless the user specifies otherwise.
Read `~/.claude/design-guidelines.md` for the full token system (colors, typography, components, spacing).
Core brand: `#E94D35` coral accent, Inter font, clean/warm/professional aesthetic.

When the user asks for something personal, internal, or company-facing, always apply brand tokens.
When building for a different context (client project, demo for another company), ask or infer.

## Design Thinking

Before coding, understand the context and commit to a BOLD aesthetic direction:
- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick an extreme: brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian, etc. There are so many flavors to choose from. Use these for inspiration but design one that is true to the aesthetic direction.
- **Constraints**: Technical requirements (framework, performance, accessibility).
- **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember?

**CRITICAL**: Choose a clear conceptual direction and execute it with precision. Bold maximalism and refined minimalism both work - the key is intentionality, not intensity.

Then implement working code (HTML/CSS/JS, React, Vue, etc.) that is:
- Production-grade and functional
- Visually striking and memorable
- Cohesive with a clear aesthetic point-of-view
- Meticulously refined in every detail

## Frontend Aesthetics Guidelines

Focus on:
- **Typography**: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics; unexpected, characterful font choices. Pair a distinctive display font with a refined body font.
- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes.
- **Motion**: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions. Use scroll-triggering and hover states that surprise.
- **Spatial Composition**: Unexpected layouts. Asymmetry. Overlap. Diagonal flow. Grid-breaking elements. Generous negative space OR controlled density.
- **Backgrounds & Visual Details**: Create atmosphere and depth rather than defaulting to solid colors. Add contextual effects and textures that match the overall aesthetic. Apply creative forms like gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, and grain overlays.

NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts), cliched color schemes (particularly purple gradients on white backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character.

Interpret creatively and make unexpected choices that feel genuinely designed for the context. No design should be the same. Vary between light and dark themes, different fonts, different aesthetics. NEVER converge on common choices (Space Grotesk, for example) across generations.

**IMPORTANT**: Match implementation complexity to the aesthetic vision. Maximalist designs need elaborate code with extensive animations and effects. Minimalist or refined designs need restraint, precision, and careful attention to spacing, typography, and subtle details. Elegance comes from executing the vision well.

Remember: Claude is capable of extraordinary creative work. Don't hold back, show what can truly be created when thinking outside the box and committing fully to a distinctive vision.

---

## Memory & Learned Preferences

This skill learns user preferences over time to deliver more personalized designs.

**Memory file:** Check the auto-memory directory for `frontend-design.md`:
```bash
cat "$(find ~/.claude/projects -name 'frontend-design.md' -path '*/memory/*' 2>/dev/null | head -1)" 2>/dev/null || echo "NOT_FOUND"
```

### Loading preferences (at skill start)

Before the design thinking phase, check for saved preferences. If found, load and auto-apply:

```
Learned preferences loaded:
├─ Preferred aesthetic: [e.g. "brutalist", "luxury refined"]
├─ Font choices: [e.g. "loves Clash Display + Cabinet Grotesk"]
├─ Color tendencies: [e.g. "prefers dark themes with warm accents"]
└─ Framework: [e.g. "always uses React + Tailwind"]
```

Use these to inform design direction — don't ask about preferences that are already saved.

### What to save after each run

At the end of every design session, update the memory file with:

- **Aesthetic preferences** — which styles the user approved, praised, or requested
- **Font pairings** — specific fonts the user liked or explicitly chose
- **Color preferences** — dark/light themes, specific palettes, accent colors
- **Framework/tech preferences** — React vs vanilla, Tailwind vs custom CSS, etc.
- **Design patterns** — preferred layouts, component styles, animation approaches
- **Anti-preferences** — things the user rejected or asked to avoid (e.g. "no gradients", "no rounded corners")
- **Feedback corrections** — design choices the user overrode (learn from these)

Use the Edit tool to update existing entries — never duplicate. Save to `~/.claude/projects/-Users-sharan-Projects/memory/frontend-design.md`.

### What NOT to save

- Specific project content or copy
- One-time overrides the user explicitly marked as temporary

## Dependency Check (Step 0a)
- If generating React/Vue components: verify `node` and `npm` are available (`which node && which npm`). Abort with install instructions if missing.
- If generating vanilla HTML: no external dependencies required, proceed directly.

## Input Validation
- Confirm the user has provided design requirements (component type, purpose, or audience). If the request is just "build something", ask for at least a purpose and context before starting.
- If a specific framework is requested (React, Vue, Svelte), verify it matches available tooling before generating code.

## Deliverables

**Always end with the deliverables block after generating the output:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  [Type] (HTML):    /absolute/path/to/output.html
                    Open in any browser to view

  [Type] (React):   /absolute/path/to/Component.tsx
                    Import into your project
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Show only the files that were actually produced (HTML, React, Vue, etc.).

## Error Handling
- **Asset not found:** If `~/.claude/design-guidelines.md` or brand assets are missing, warn the user and fall back to the skill's built-in aesthetic guidelines.
- **Component render failure:** If generated HTML/JS has syntax errors during browser preview, surface the error and offer to fix the specific broken section.
- **Framework mismatch:** If the user requests a framework not installed locally, suggest vanilla HTML/CSS/JS as an alternative rather than failing silently.

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-13 | Pre-Flywheel baseline (existing behavior, no standard sections) |
