# Vendored JS

- `mermaid.min.js` — mermaid.js 10.9.1 UMD build, downloaded from
  `https://registry.npmjs.org/mermaid/-/mermaid-10.9.1.tgz` (`package/dist/mermaid.min.js`).
  Vendored instead of pulled from a CDN so `components/mermaid.py` can render
  diagrams offline / behind networks that block third-party JS. To update,
  download a newer `mermaid-<version>.tgz` from the npm registry and replace
  this file with its `package/dist/mermaid.min.js`.
