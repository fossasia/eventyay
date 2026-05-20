import re
from urllib.request import urlopen


def fetch_vite_html(vite_dev_server):
    """Fetch index.html from a Vite dev server and rewrite asset URLs to absolute."""
    with urlopen(f'{vite_dev_server}/index.html') as resp:
        html = resp.read().decode('utf-8')
    html = re.sub(r'(src|href)="(/(?![/#]))', rf'\1="{vite_dev_server}\2', html)
    html = re.sub(r'(src|href)="(\./)', rf'\1="{vite_dev_server}/', html)
    return html
