# Hosting a show under a URL

Hosting is optional: the built file on the presenting machine, plus a copy on a USB stick, never depends on venue wifi. Host it only when the venue's machine must open a URL, or the show should stay reachable after the event.

- **Material under its owner's usage rules** (stagecraft.md, Content): its terms usually cover the talk, not the web, social posts or email. Without the owner's permission for that use, a show carrying it stays a local file, or the hosted copy leaves it out.
- **Review first, privately:** drafts go under a URL only the reviewers reach (a VPN or tailnet, or a password-protected host). A public URL is for the event.
- **Any static host** serves `dist/<slug>.html` as is; gzip is optional. Present from https or the local file: over plain `http://`, a tailnet or LAN link included, the browser grants no screen wake lock and the presenting machine may sleep. When the audience opens the show on their own phones, run qa.md's phone check first.
- **Size:** hosts cap file sizes. A Kubernetes ConfigMap holds at most 1 MiB, so a show stored there gzipped needs `gzip -9 -n -c dist/<slug>.html | wc -c` below 1048576. Shrink photos first.
- **Public means everything in the file**, the speaker notes included (N shows them). Check that it holds nothing internal; a wifi password the venue displays anyway is fine.
- **Update:** upload the new build, then compare `curl -s --compressed <url> | sha256sum` with `sha256sum dist/<slug>.html` (macOS: `shasum -a 256`). When a cache serves the old copy, purge it or wait, and compare again.
- **After the event:** ask the user whether to take the show down, then remove everything that made it reachable (files, routes, DNS records).
