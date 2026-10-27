# tongwang.digital

Personal academic website of Tong Wang, served at https://www.tongwang.digital/ by Netlify
(site `wang-tong-289211`), which builds every push to `master` and a preview for every pull request.

The site is plain [Hugo](https://gohugo.io/) (0.140, no theme or modules): a handful of templates in
`layouts/`, one stylesheet in `assets/css/site.css`, one small script in `assets/js/site.js` (the network
behind the page titles and the typed tagline), and two data files. The design is dark, with a light
palette for visitors whose system is set to light; the three accent colours stand for the three research
lines.

| File | What | Edit by hand? |
|---|---|---|
| `data/cv.json` | Positions, education, publications, books, grants, teaching, awards, service and talks | No: generated from the CV |
| `data/extra.yaml` | Tagline, biography, the About paragraph, the Zhihu and Bilibili links, research lines, DOIs, abstracts, English glosses of the Chinese books, course descriptions, contact details, selected publications for the home page | Yes |
| `content/*.md` | One stub per page; the page bodies come from the templates | Rarely |
| `static/_redirects` | Redirects from the old Hugo Blox URLs | Rarely |

## Updating after a CV change

The CV in the grants repository (`~/projects/grants/cv/cv_simple.tex` and `cv_simple_zh.tex`) is the
single source. After changing it:

```sh
python3 scripts/cv_to_data.py      # rewrites data/cv.json; needs PyYAML
hugo server                        # check locally at http://localhost:1313/
git add data/cv.json && git commit -m "Update from CV" && git push
```

The script stops with a message if the CV gains a section it does not know, or if an entry in
`data/extra.yaml` no longer matches the CV (for example after a paper is retitled); fix the entry and run
it again. Working papers and work in progress are never copied to the site: the repository is public.

## Images

The portrait `static/img/tong-wang.jpg` is a 400 px copy. The original photo is kept in Dropbox through
`showcase files` (`media-src/avatar-original.jpg`; `showcase files pull` restores it).

`static/img/tong-wang-cut.webp` is the same photo with the background removed (320 px), used in the
round portrait on the home and Chinese pages; the full-size cutout is `media-src/avatar-cutout.png`, also
in Dropbox. These two images are the only binaries kept in the repository, besides the fonts.

## Fonts

`static/fonts/` holds the Latin subsets of Space Grotesk, Inter and JetBrains Mono (SIL Open Font
License, see `OFL.txt`), served from the site itself so that no visitor's browser contacts Google Fonts.
Chinese text uses the visitor's system fonts.
