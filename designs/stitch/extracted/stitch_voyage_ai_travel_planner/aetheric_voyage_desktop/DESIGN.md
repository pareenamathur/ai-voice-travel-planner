---
name: Aetheric Voyage Desktop
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#393939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#d4c0d7'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#9d8ba0'
  outline-variant: '#514255'
  surface-tint: '#ecb2ff'
  primary: '#ecb2ff'
  on-primary: '#520071'
  primary-container: '#bd00ff'
  on-primary-container: '#ffffff'
  inverse-primary: '#9900cf'
  secondary: '#d3fbff'
  on-secondary: '#00363a'
  secondary-container: '#00eefc'
  on-secondary-container: '#00686f'
  tertiary: '#ffb961'
  on-tertiary: '#472a00'
  tertiary-container: '#a66800'
  on-tertiary-container: '#fffeff'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#f8d8ff'
  primary-fixed-dim: '#ecb2ff'
  on-primary-fixed: '#320047'
  on-primary-fixed-variant: '#74009f'
  secondary-fixed: '#7df4ff'
  secondary-fixed-dim: '#00dbe9'
  on-secondary-fixed: '#002022'
  on-secondary-fixed-variant: '#004f54'
  tertiary-fixed: '#ffddb9'
  tertiary-fixed-dim: '#ffb961'
  on-tertiary-fixed: '#2b1700'
  on-tertiary-fixed-variant: '#663e00'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
typography:
  display-xl:
    fontFamily: Geist
    fontSize: 72px
    fontWeight: '700'
    lineHeight: 80px
    letterSpacing: -0.04em
  headline-lg:
    fontFamily: Geist
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
    letterSpacing: '0'
  body-md:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: '0'
  label-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.05em
  mono-sm:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: '0'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  page-margin: 64px
  gutter: 32px
  section-gap: 120px
  stack-sm: 12px
  stack-md: 24px
  stack-lg: 48px
---

## Brand & Style

The design system is a high-fidelity, immersive environment designed for deep focus and technical exploration. It targets a sophisticated audience that appreciates the intersection of cutting-edge technology and cosmic exploration. The aesthetic is rooted in **Glassmorphism** and **Minimalism**, creating a sense of depth and atmospheric clarity.

The UI should evoke a feeling of "weightless precision"—where complex data feels light and navigable. This is achieved through the use of expansive whitespace, translucent layering, and sharp, high-contrast typography that cuts through the atmospheric background blurs.

## Colors

This design system utilizes a deep, multi-layered dark palette to simulate the infinite depth of space. 

- **Primary (Nebula Purple):** Used for primary actions, active states, and critical paths.
- **Secondary (Cyber Cyan):** Used for data visualization, highlights, and secondary interactions to provide a high-energy contrast.
- **Surface (Dark Charcoal):** The foundation of the UI. Backgrounds use a pure `#121212`, while elevated glass panels use semi-transparent variations of `#1A1A1A`.
- **Gradients:** Use linear gradients from Primary to Secondary (at 45 degrees) for high-impact display elements.

## Typography

Geist is the exclusive typeface for this design system, chosen for its technical precision and readability in dark environments. 

- **Headlines:** Use Bold or SemiBold weights. For display sizes, apply a slight negative letter-spacing to enhance the "engineered" feel.
- **Body:** Stick to Regular weight for maximum legibility against dark backgrounds.
- **Labels:** Use Medium weight with increased tracking and uppercase styling for a "instrument panel" aesthetic.
- **Contrast:** Ensure all text on glass surfaces maintains a minimum 4.5:1 contrast ratio, often requiring pure white (#FFFFFF) or very light grey (#E4E4E4).

## Layout & Spacing

This design system employs a **12-column fluid grid** optimized for large-format desktop displays (1440px and above). 

- **Generous Breathing Room:** The gutter size is increased to 32px to prevent visual clutter and maintain the minimalist aesthetic.
- **Vertical Rhythm:** A base 8px grid governs all micro-spacing. Component-level spacing follows a geometric progression (8, 16, 24, 32, 48, 64).
- **Margins:** Page margins are set to 64px, ensuring content feels centered and prestigious rather than cramped against the edge of the viewport.

## Elevation & Depth

Depth is the defining characteristic of this design system, achieved through **Glassmorphism** and strategic layering.

1.  **The Void (Base):** The bottom-most layer, solid `#121212`.
2.  **Atmospheric Blur (Mid):** Glass panels use a background blur of 20px to 40px and a fill of `#FFFFFF05` (light) or `#00000040` (dark).
3.  **The Lens (High):** Active elements or modals use a sharper 1px inner border (stroke) with a gradient from top-left (`#FFFFFF20`) to bottom-right (`#FFFFFF05`) to simulate light hitting an edge.
4.  **Glow:** High-elevation elements emit a soft, low-opacity glow using the Primary or Secondary color (e.g., `0 20px 40px -10px rgba(189, 0, 255, 0.2)`).

## Shapes

The shape language balances structural rigidity with organic softness. 

- **Cards & Primary Containers:** Specifically use a **20px corner radius** to create a distinct "pod" or "capsule" look.
- **Buttons & Inputs:** Follow the standard 8px (0.5rem) roundedness for a more tactical, precise feel.
- **Interactive States:** Use subtle scaling (1.02x) on hover for glass panels to enhance the tactile nature of the UI.

## Components

### Buttons
- **Primary:** Solid Purple-to-Cyan gradient background with white Geist SemiBold text.
- **Secondary:** Ghost style with a 1px border using `#FFFFFF20` and a backdrop blur of 12px.
- **Hover States:** Increase the brightness of the gradient or increase the backdrop blur intensity.

### Cards
- **Construction:** 20px corner radius, 1px subtle white border at 10% opacity, 30px backdrop blur.
- **Padding:** 32px internal padding to match the layout's generous gutter.

### Inputs & Selects
- Filled with `#FFFFFF08`, 8px roundedness, and a 1px border that glows Cyan on focus. Labels should sit 8px above the field in Label-MD typography.

### Lists & Navigation
- Navigation items use a 1px Cyan underline that expands from the center on hover.
- List items are separated by subtle horizontal lines (`#FFFFFF05`) rather than heavy borders.

### Progress Indicators
- Use the Secondary Cyan for progress bars, with a faint glow effect and a Primary Purple trailing edge to suggest movement.