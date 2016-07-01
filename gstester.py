#!/usr/bin/env python3

"""
Google Sitemap Tester
"""

import argparse
import sys
import os
import shutil
import urllib.request
from urllib.parse import urlparse
import http.client
import gzip
import re
import xml.etree.ElementTree as ET
from queue import Queue
from threading import Thread
import random

"""
Main function
"""
_tmp_dir = './tmp'
_xml_ns = {
    'default': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'xhtml'  : 'http://www.w3.org/1999/xhtml',
    'image'  : 'http://www.google.com/schemas/sitemap-image/1.1'
}
_user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.110 Safari/537.36'

_args = object
_curr_stats_id = -1
_stats = []
_page_urls = []
_image_urls = []
link_queue = Queue()

def main():
    global _args
    # Define script arguments
    argparser = argparse.ArgumentParser(description='Google Sitemap Tester')
    argparser.add_argument('urls', metavar='URL', type=str, nargs='+', help='Sitemap urls to be processed')
    #argparser.add_argument('-n', '--no-check', action='store_const', const=True, default=False, help='Do not check links found in sitemaps')
    argparser.add_argument('-c', '--connections', metavar='C', action='store', default=5, type=int, help='Max number of simultaneous connections when checking links')
    argparser.add_argument('-r', '--random-check', metavar='N', action='store', default=0, type=int, help='Check NUM random links')
    _args = argparser.parse_args()

    # Clean temp dir
    clean_dir(_tmp_dir)

    try:
        for idx, url in enumerate(_args.urls, start=1):
            process_url(url)
        print_stats()

        if _args.random_check > 0:
            print('\nChecking {0} random page links...'.format(_args.random_check))
            random_check_links(_args.random_check, _args.connections, _page_urls)
            print('\nChecking {0} random image links...'.format(_args.random_check))
            random_check_links(_args.random_check, _args.connections, _image_urls)
    except KeyboardInterrupt:
        print('\nGot keyboard interrupt. Exiting')

    return 0

"""
Program functions
"""
def clean_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        return
    shutil.rmtree(dir_path)
    os.makedirs(dir_path)

def process_url(url):
    global _stats, _curr_stats_id
    # Init stats
    _curr_stats_id += 1
    _stats.append({
        'url': url,
        'download': '-',
        'parse': '-',
        'type': '-',
        'sitemap_urls': '-',
        'page_urls': '-',
        'image_urls': '-'
    })

    # Download url
    print('\nDownloading %s ...' % url)
    res = download(url)
    if res['success']:
        path = res['path']
        _stats[_curr_stats_id]['download'] = 'ok'
    else:
        print('Error:', res['error'])
        print('Skipping')
        _stats[_curr_stats_id]['download'] = 'error'
        return 3

    # Gunzip if needed
    if path.endswith('.gz'):
        print('Unpacking %s ...' % path)
        path = gunzip(path)

    # Load XML
    print('Parsing XML...', end="")
    res = load(path)
    if res['success']:
        print(' XML successfully loaded')
        xml_tree = res['tree']
        _stats[_curr_stats_id]['parse'] = 'ok'
    else:
        print('Error:', res['error'])
        print('Skipping')
        _stats[_curr_stats_id]['parse'] = 'error'
        return 2

    xml_type = get_type(xml_tree)

    # Get XML type (sitemap | sitemap index)
    _stats[_curr_stats_id]['type'] = xml_type
    if xml_type == 'unknown':
        print('Unknown XML type. Skipping')
        return 1
    elif xml_type == 'index':
        process_index(xml_tree, url)
    elif xml_type == 'sitemap':
        process_sitemap(xml_tree, url)

def process_index(xml, xml_url):
    global _stats, _curr_stats_id
    sitemap_urls = get_urls_from_index(xml)
    print('  %d sitemap URLs found' % len(sitemap_urls))
    _stats[_curr_stats_id]['sitemap_urls'] = len(sitemap_urls)
    for url in sitemap_urls:
        process_url(url)

def process_sitemap(xml, xml_url):
    global _stats, _curr_stats_id
    page_urls  = get_page_urls(xml)
    image_urls = get_image_urls(xml)
    _page_urls.extend(page_urls)
    _image_urls.extend(image_urls)
    _stats[_curr_stats_id]['page_urls'] = len(page_urls)
    _stats[_curr_stats_id]['image_urls'] = len(image_urls)

def print_stats():
    global _stats
    print(" ")
    row_format = "{:>30}{:>10}{:>7}{:>9}{:>14}{:>11}{:>12}"
    print(row_format.format('URL', 'Download', 'Parse', 'Type', 'Sitemap urls', 'Page urls', 'Image urls'))
    for sitemap in _stats:
        print(row_format.format(
            '...' + sitemap['url'][-27:],
            sitemap['download'],
            sitemap['parse'],
            sitemap['type'],
            sitemap['sitemap_urls'],
            sitemap['page_urls'],
            sitemap['image_urls']
        ))

def download(url):
    # Get file name
    filename = url.split('/')
    filename = filename[len(filename) - 1]
    out_path = os.path.join(_tmp_dir, filename)
    try:
        req = urllib.request.Request(url, data=None, headers={'User-Agent': _user_agent})
        with urllib.request.urlopen(req) as in_file, open(out_path, 'wb') as out_file:
            out_file.write(in_file.read())
        return {
            'success': True,
            'path': out_path
        }
    except Exception as e:
        return {
            'success': False,
            'error': e
        }

def gunzip(path):
    out_path = path.replace('.gz', '')
    with open(path, 'rb') as in_file, open(out_path, 'wb') as out_file:
        out_file.write(gzip.decompress(in_file.read()))
    return out_path

def load(path):
    try:
        tree = ET.parse(path)
        return {
            'success': True,
            'tree': tree
        }
    except Exception as e:
        return {
            'success': False,
            'error': e
        }

def get_type(xml):
    root = xml.getroot()

    # Tag with namespace looks like '{http://some.namespace}tagname'
    # Removing the namespace part in order to recognize it
    root = re.sub(r'^{.+}', '', root.tag)

    if root == 'sitemapindex':
        return 'index'
    elif root == 'urlset':
        return 'sitemap'
    else:
        return 'unknown'

def get_page_urls(xml):
    out = []
    for url in xml.findall('default:url', _xml_ns):
        out.append(url.find('default:loc', _xml_ns).text)
    return out

def get_image_urls(xml):
    out = []
    for url in xml.findall('default:url', _xml_ns):
        for image in url.findall('image:image', _xml_ns):
            out.append(image.find('image:loc', _xml_ns).text)
    return out

def get_urls_from_index(xml):
    out = []
    for sitemap in xml.findall('default:sitemap', _xml_ns):
        out.append(sitemap.find('default:loc', _xml_ns).text)
    return out

def random_check_links(links_num, connections, urls):
    if connections < 1:
        connections = 1

    # Fill queue
    for i in range(links_num):
        link_queue.put(random.choice(urls))

    # Init threads
    for i in range(connections):
        worker = Thread(target=random_check_links_worker, args=(i, link_queue))
        worker.setDaemon(True)
        worker.start()

    # Wait for the queue to be empty
    link_queue.join()

def random_check_links_worker(i, q):
    while not q.empty():
        url = q.get()
        res = check_link(url)
        out_format = '[{2}{0}{3}] {1}'
        if 200 <= res < 300:
            print(out_format.format(res, url, ccolor.green, ccolor.end))
        if 300 <= res < 400:
            print(out_format.format(res, url, ccolor.yellow, ccolor.end))
        if 400 <= res < 500:
            print(out_format.format(res, url, ccolor.red, ccolor.end))
        if 500 <= res < 600:
            print(out_format.format(res, url, ccolor.blue, ccolor.end))
        q.task_done()

def check_link(url):
    url_parsed = urlparse(url)
    conn = http.client.HTTPConnection(url_parsed.netloc)
    conn.request('HEAD', url_parsed.path, headers={'User-Agent': _user_agent})
    return conn.getresponse().status

"""
Console colors class
"""
class ccolor:
    end    = '\033[39m'
    green  = '\033[92m'
    yellow = '\033[93m'
    red    = '\033[91m'
    blue   = '\033[94m'

##############################
if (__name__ == '__main__'):
    sys.exit(main())
