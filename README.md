# Google Sitemap Tester
Simple Python3 script which tests Google-compliant sitemaps

```
usage: gstester.py [-h] [-c C] [-r N] URL [URL ...]

positional arguments:
  URL                   Sitemap urls to be processed

optional arguments:
  -h, --help            show this help message and exit
  -c C, --connections C
                        Max number of simultaneous connections when checking
                        links
  -r N, --random-check N
                        Check NUM random links
```

URL can also be a sitemap index: sitemap files linked in the index will be downloaded and checked automatically.
