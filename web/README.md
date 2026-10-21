# MacroTracker website

A small React + TypeScript site (built with Vite) that explains MacroTracker
and shows a working demo of the Discord bot. Hosted on GitHub Pages.

## Run it

```bash
cd web
npm install        # first time only
npm run dev        # http://localhost:5173/MacroTracker/ with live reload
npm run build      # type-check and build to web/dist/
npm run preview    # serve the built site locally
```

Pushing changes under `web/` to `main` publishes the site automatically
(`.github/workflows/pages.yml`).

## How it's organized

```
web/src/
├── main.tsx, App.tsx      Entry point; routes come from pages/registry.tsx
├── pages/
│   ├── registry.tsx       Every page: path, browser-tab title, content
│   ├── SectionPage.tsx    Renders a page as a stack of sections
│   └── NotFoundPage.tsx
├── sections/
│   ├── registry.ts        The home page's sections, top to bottom
│   ├── types.ts           The Section type every entry follows
│   └── Banner, Hero, HowItWorks, DiscordDemo (.tsx + .module.css)
├── components/            Reusable pieces: SectionShell, ButtonLink, Layout
│   └── discord/           Mock Discord UI: message, embed, buttons, markdown
├── content/
│   ├── site.ts            All wording and links
│   └── demo.json/.ts      Demo data generated from the real bot
└── styles/global.css      Design tokens (colors, sizes) and base styles
```

Each component has its own `.module.css`, so styles never leak between
components.

## Add a section

1. Create `src/sections/Faq.tsx` (and `Faq.module.css`), usually wrapping its
   content in `<SectionShell id="faq" title="...">`.
2. Add one line to `src/sections/registry.ts`:
   `{ id: "faq", navLabel: "FAQ", component: Faq }`.

## Add a page

1. Create its sections, or a component, e.g. a list `aboutSections`.
2. Add one entry to `src/pages/registry.tsx`:
   `{ path: "/about", title: "About · MacroTracker", element: <SectionPage sections={aboutSections} /> }`.
3. Link to it with React Router's `<Link to="/about">`.

## Change the banner

The picture banner at the top of the home page is set in `banner` in
`src/content/site.ts`.

1. Put your picture in `web/public/banner/`, e.g. `banner.jpg`. Wide pictures
   work best (about 3:1, such as 1600 × 500); JPG or WebP under ~500 KB loads
   quickly.
2. In `site.ts`, set `src: "banner/banner.jpg"` and describe the picture in
   `alt`.
3. Optional: change or remove `caption` (the text over the picture), or set
   `focus` (e.g. `"top"`) to choose which part of a very tall picture stays
   visible.
4. To hide the banner, set `banner` to `null`. To move it, move its line in
   `src/sections/registry.ts`.

The banner keeps the picture's own shape, so nothing is cut off on phones; on
small screens the caption moves below the picture. If the file can't be
loaded, the banner hides itself instead of showing a broken image.

## Refresh the demo

The demo's chart images and card text are generated from the bot's own code,
so they always match what the bot sends. After changing the bot's charts or
embeds, from the project root:

```bash
.venv/bin/python web/scripts/generate_demo.py
```

## Before sharing

`site.links.requestAccess` in `src/content/site.ts` points to the GitHub
profile; change it to wherever people should ask for an invite.
