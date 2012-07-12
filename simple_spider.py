"""MultiThreading Web Spider For Downloading Wallpapers from Sites with Unicode Paths"""

import HTMLParser
import os
import re
import threading
import time
import urllib2
import urlparse


class ImageGetter(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.base_dir = '.'
        self.delay = .1 # seconds
        
    def run(self):
        global image_url_stack
        while True:
            # pop the top of the stack(if not empty) and retrieve and save to file
            image_url = ''
            if image_url_stack.has_url():
                image_url = image_url_stack.pop()
            if image_url:
                success = self.get_image_url(image_url)
                image_url_stack.processed(image_url, success)
            time.sleep(self.delay)

    def get_image_url(self, image_url):
        global os_lock
        try:
            u = urllib2.urlopen(image_url)
        except:
            print "Error in Img Get: " + image_url
            return False
        # http://www.something.com/dir/subdir/file.ext  --> /dir/subdir/file.ext
        path = urlparse.urlsplit(image_url).path
        path = urllib2.unquote(path)
        # /dir/subdir/file.ext  --> /dir/subdir
        directory, filename = os.path.split(path)
        os_lock.acquire()
        if not os.path.exists(self.base_dir + directory):
            os.makedirs(self.base_dir + directory)
        os_lock.release()
        # base_dir + /path/file.ext  --> base_dir/path/file.ext
        f = open(self.base_dir + path, 'wb')
        f.write(u.read())
        f.close()
        return True


class PageGetter(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.delay = .1 # seconds
        
    def run(self):
        global page_url_stack
        while True:
            # pop the top of the stack(if not empty) and retrieve and append to lists
            page_url = ''
            if page_url_stack.has_url():
                page_url = page_url_stack.pop()
            if page_url:
                success = self.get_page_url(page_url)
                page_url_stack.processed(page_url, success)
            time.sleep(self.delay)

    def get_page_url(self, page_url):
        global os_lock
        global image_url_stack
        global page_url_stack
        
        try:
            u = urllib2.urlopen(page_url)
        except:
            print "Error is Page Get: " + page_url
            return False
        text = u.read()
          
        # Find Images
        #  Simple hack to account for both single and double quotes(a single regex is nigh unreadable)
        img_regex = re.compile("src\s*=\s*'(.*?jpg|jpeg)'", re.I + re.U)
        img_regex2 = re.compile('src\s*=\s*"(.*?jpg|jpeg)"', re.I + re.U)
        #print "IMG LINKS:" + str(img_regex.findall(text) + img_regex2.findall(text))
        img_links = img_regex.findall(text) + img_regex2.findall(text)
        # Change Relative Links to Absoulte Links
        img_links = [urlparse.urljoin(page_url, link) for link in img_links]
        image_url_stack.append_multiple(img_links)
    
        # Find Pages
        #  Simple hack to account for both single and double quotes(a single regex is nigh unreadable)
        page_regex = re.compile("href\s*=\s*'(.*?)'", re.I + re.U)
        page_regex2 = re.compile('href\s*=\s*"(.*?)"', re.I + re.U)
        page_links = page_regex.findall(text) + page_regex2.findall(text)
        # Change Relative Links to Absoulte Links
        page_links = [urlparse.urljoin(page_url, link) for link in page_links]
        page_url_stack.append_multiple(page_links)

        return True
        
class URLStack(object):
    def __init__(self):    
        self.url_stack = []
        self.processed_urls = []
        self.domains = []
        self.paths = []
        self.lock = threading.RLock()
    
    def __len__(self):    
        self.lock.acquire()
        length = len(self.url_stack)
        self.lock.release()
        return length
    
    def pop(self):
        self.lock.acquire()
        url = None
        if self.url_stack:
            url = self.url_stack.pop()
        self.lock.release()
        return url
        
    # Accepts single item(string)
    def processed(self, item, success):
        self.lock.acquire()
        if success:
            self.processed_urls.append(item)
        else:
            self.url_stack.insert(0, item)
        self.lock.release()

    def has_url(self):
        self.lock.acquire()
        has_url = len(self.url_stack) > 0
        self.lock.release()
        return has_url
        
    # Accepts single item(string)
    def append_single(self, item):
        self.lock.acquire()
        parsed_item = urlparse.urlsplit(item)
        if item not in self.url_stack and item not in self.processed_urls and parsed_item.netloc.endswith(tuple(self.domains)) and urllib2.unquote(parsed_item.path).startswith(tuple(self.paths)):
            self.url_stack.append(item)
        self.lock.release()

    # Accepts iterable(list, tuple, ...), do not send string
    def append_multiple(self, items):
        self.lock.acquire()
        for item in items:
            self.append_single(item)
        self.lock.release()
    
def main():
    global image_url_stack
    global page_url_stack
    global os_lock
    image_url_stack = URLStack()
    page_url_stack = URLStack()
    os_lock = threading.Lock()
    
    page_url_stack.domains.append('my.opera.com')
    #image_url_stack.domains.append('my.opera.com')
    image_url_stack.domains.append('files.myopera.com')
    
    # utf-8 is the standard of path of unicode urls
    path_utf8 = '/\xe8\xac\x8e\xe3\x81\xae\xe5\x85\x83\xe6\xb0\x97\xe9\x85\x8d\xe9\x81\x94\xe4\xba\xba/albums/'
    page_url_stack.paths.append(path_utf8)
    image_url_stack.paths.append(path_utf8)
    
    # utf-8, url quoted (percent encoding)
    url = "http://my.opera.com/%E8%AC%8E%E3%81%AE%E5%85%83%E6%B0%97%E9%85%8D%E9%81%94%E4%BA%BA/albums/"
    page_url_stack.append_single(urllib2.unquote(url))
    
    for i in xrange(5):
        pg = PageGetter()
        pg.start()
    
    for i in xrange(8):
        ig = ImageGetter()
        ig.base_dir = 'download'
        ig.start()
    
    # Try to capture Ctrl-C and exit if caught
    try:
        while True:
            time.sleep(3)
            print "Image Stack Length:" + str(len(image_url_stack)) + "Page Stack Length:" + str(len(page_url_stack))
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()