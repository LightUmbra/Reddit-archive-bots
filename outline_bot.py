#!/usr/bin/python3

contact_info = "" #Your username or subreddit name, with /u/ or /r/ included. Needed so users can contact you. If a sub name is used, modmail will be sent to that sub.
working_sub = "" #The sub you want the bot to run in. Exclude the /r/.
bot_UN = "BussyShillBot" #The bot's username. Should be the same as the name in brackets in your praw.ini file (e.g. [OutlineBot1]). Exclude the /u/.
skip_sites = ["reddit.com","redd.it","redditmedia.com","imgur.com","twitter.com","youtube.com","youtu.be","giphy.com"] #sets sites for Outline.com to skip
footer_text = "I am a bot for posting Outline.com links." #This text is let people know the purpose of the bot
INFO = ""

import logging
import os
import praw
import re
import random
import requests
import time
import traceback
import warnings
import urllib.request
from bs4 import BeautifulSoup
from html.parser import unescape
from urllib.parse import urlencode
from praw.exceptions import APIException, ClientException
from prawcore.exceptions import RequestException, ResponseException, OAuthException

DEBUG = False
CONTACT = "/message/compose?to=\{UN}".format(UN=contact_info)
USER_AGENT = "Creates Outline.com links for linked websites" 
ARCHIVE_ORG_FORMAT = "%Y%m%d%H%M%S"
MEGALODON_JP_FORMAT = "%Y-%m%d-%H%M-%S"
LEN_MAX = 35
REDDIT_API_WAIT = 10
WARN_TIME = 300 #warn after spending 5 minutes on a post
skip_ext = ["jpg","png","gif","gifv","mp4","jpeg","pdf","tiff","avi"] #file extensions to skip
reddit = praw.Reddit(bot_UN, user_agent=USER_AGENT)
wait = 5

REDDIT_PATTERN = re.compile("https?://(([A-z]{2})(-[A-z]{2})"
                            "?|old|beta|i|m|pay|ssl|www)\.?reddit\.com")
SUBREDDIT_OR_USER = re.compile("/(u|user|r)/[^\/]+/?$")

site_pattern = [re.compile("https?://(([A-z]{{2}})(-[A-z]{{2}})""?|old|beta|i|m|pay|ssl|www)\.{SITE}".format(SITE=sites)) for sites in skip_sites]
ext_pattern = [re.compile("\.{EXT}($|\?)".format(EXT=ext)) for ext in skip_ext]

ignorelist = set()

RECOVERABLE_EXC = (APIException,
                   ClientException,
                   ResponseException,
                   RequestException,
                   OAuthException)

loglevel = logging.DEBUG if DEBUG == True else logging.INFO

logging.basicConfig(level=loglevel,
                    format="[%(asctime)s] [%(levelname)s] %(message)s")

log = logging.getLogger(bot_UN)
logging.getLogger("requests").setLevel(loglevel)
warnings.simplefilter("ignore")  # Ignore ResourceWarnings (because screw them)


# If we have not run the code before, start an empty list for submission ids. A file for saving ids is made elsewhere. If it has ben run load the ids of posts we have replied into a list
if not os.path.isfile("{SUB}_posts_replied_to.txt".format(SUB=working_sub)):
    posts_replied_to = []
    
# Read the file into a list and remove any empty values
else:
    with open("{SUB}_posts_replied_to.txt".format(SUB=working_sub), "r") as f:
        posts_replied_to = f.read()
        posts_replied_to = posts_replied_to.split("\n")
        posts_replied_to = list(filter(None, posts_replied_to))
        
#If a quote file does not exist, do not include quotes. Otherwise, read quotes from file into list for later use.
if not os.path.isfile("{SUB}_quotes.txt".format(SUB=working_sub)):
    log.warn("There is no file for quotes. If you want quotes, create a file called {}_quotes.txt. Refer to the README for instructions on building the quote file.".format(working_sub))
    incl_quotes = False
    quotes = ['']
else:
    with open("{SUB}_quotes.txt".format(SUB=working_sub), encoding='utf-8') as quote_file:
        quotes = [q.strip() for q in re.split('\n-{2,}\n', quote_file.read()) if q.strip()]
        quote_file.close()
    incl_quotes = True

def fix_url(url):
    """
    Change language code links, mobile links and beta links, SSL links and
    username/subreddit mentions
    :param url: URL to change.
    :return: Returns a fixed URL
    """
    if url.startswith("/r/") or url.startswith("/u/"):
        fixedurl = "http://www.reddit.com{URL}".format(URL=url)
        return fixedurl
    else:
        return url

def skip_url(url): #Determines whether to skip a site when it's linked in a text post.
    """
    Skip naked username mentions and subreddit links.
    """  
    for patterns in site_pattern: # uses for loop and regexp to search for skipped sites in URLs
        if len(re.findall(patterns, url)) > 0:
            log.debug("site: true - skipping")
            return True
            break
        else:
            for ext in ext_pattern: # uses for loop and regexp to search for skipped sites in URLs
                if len(re.findall(ext, url)) > 0:
                    log.debug("site: false ext: True - skipping")
                    return True
                    break
                else:
                    log.debug("site: false ext: false")
                    return False
            
def skip_sub_url(submission): #Determines whether a post is a link post and skips it if the link is to a skipped site.
    """
    Skip naked username mentions and subreddit links.
    """
    url = submission.url
    if submission.is_self: #determines whether the post is a text post. If it is, any links in the post will be checked by skip_url() later.
        log.debug("Self post: true - skipping")
        return False
    else:
        for patterns in site_pattern: # uses for loop and regexp to search for skipped sites in URLs
            if len(re.findall(patterns, url)) > 0:
                log.debug("site: true - skipping")
                return True
                break
            else:
                for ext in ext_pattern: # uses for loop and regexp to search for skipped sites in URLs
                    if len(re.findall(ext, url)) > 0:
                        log.debug("site: false ext: True - skipping")
                        return True
                        break
                    else:
                        return False
                        log.debug("site: false ext: false")
        
def err_wait(wait): #Function for delay following a major error
    time.sleep(wait)

    if wait >= 160: #Caps the error wait time at 160 seconds.
        wait = 160
        
    else:
        wait = wait*2 #Exponential backoff when there is an error.
        
    return wait

class NameMixin:
    site_name = None

    @property
    def name(self):
        if self.archived:
            return self.site_name
        else:
            return "_{}\*_".format(self.site_name)

def ratelimit(url):
    if len(re.findall(REDDIT_PATTERN, url)) == 0:
        return
    time.sleep(REDDIT_API_WAIT)
			
class Outline(NameMixin):
    site_name = "Outline"

    def __init__(self, url):
        self.url = url
        self.archived = self.archive()
        pairs = {"url": self.url, "run": 1}
        
    def archive(self):
        log.debug("https://outline.com/{}".format(self.url))
        return "https://outline.com/{}".format(self.url)

class ArchiveContainer:
    def __init__(self, url, text):
        log.debug("Creating ArchiveContainer")
        self.text = text
        self.url = url
        self.archives = [Outline(url)]
        if "www." in self.text or "http" in self.text or ".com" in self.text:
            escaped = self.text.translate(str.maketrans({"(":  r"\(",")":  r"\)"}))
            self.text = ("["+escaped[:LEN_MAX] + "...](" + escaped + ")") if len(escaped) > LEN_MAX else escaped
        else:
            self.text = (text[:LEN_MAX] + "...") if len(text) > LEN_MAX else text

def get_footer(url):
    return "^(*{ftr_text}*) [^(*github*)](https://github.com/LightUmbra/Reddit-archive-bots) ^/ [^(*Contact for info or issues*)]({contact})".format(ftr_text=footer_text, contact=CONTACT)

class Notification:

    def __init__(self, post, links, url):
        self.post = post
        self.links = links
        self.url = url

    def notify(self):
        """
        Replies with a comment containing the archives or if there are too
        many links to fit in a comment, infome them that there are too many links and there is not a solution yet.
        """
        try:
            comment = self._build()
            if len(comment) > 9999:
                link = self.post.permalink
                comment = self.post.reply("There are too many links for me to handle and my creator was too lazy to make a sub for this.")
                log.info("Posted a comment and new submission")
            else:
                comment = self.post.reply(comment)
        except RECOVERABLE_EXC as e:
            log_error(e)
            return

    def _build(self):
        quote = random.choice(quotes)
        log.info(quote) 
        parts =  ["{}".format(quote), "Outlines:"] 
        format = "[{name}]({archive})"

        for i, link in enumerate(self.links, 1):
            subparts = []
            log.debug("Found link")

            for archive in link.archives:
                if archive.archived is None:
                    continue

                archive_link = archive.archived.translate(str.maketrans({"(":  r"\(",")":  r"\)"}))
                subparts.append(format.format(name=archive.name,
                                              archive=archive_link))

            parts.append("{}. {} - {}".format(i, link.text, ", ".join(subparts)))
        log.debug("Footer url: {}".format(urllib.parse.quote_plus(str(self.url))))
        parts.append(get_footer(self.url))

        return "\n\n".join(parts)

class OutlineBot:

    def __init__(self):
        self.headers = {}
        self._setup = False

    def run(self):
        """
        Checks through the submissions and archives and posts comments.
        """
        subreddit1 = reddit.subreddit(working_sub)

        for submission in subreddit1.stream.submissions():
            if submission.id not in posts_replied_to:
                posts_replied_to.append(submission.id)
                debugTime = time.time()
                warned = False
                log.info("Found submission.: {}".format(submission.permalink))
                with open("{}_posts_replied_to.txt".format(working_sub), "a") as posts:
                    posts.write('{}\n'.format(submission.id))
                    posts.close()

                skipped = 0
                if not skip_sub_url(submission):
                    log.debug("Self post: {}".format(submission.is_self))
                    
                    if not submission.is_self:
                        archives = [ArchiveContainer(fix_url(submission.url),"*This Post*")]
                        skipped = 1
                    
                    elif submission.is_self and submission.selftext_html is not None: #for text posts with links
                        log.debug("Found text post...")
    
                        links = BeautifulSoup(unescape(
                            submission.selftext_html)).find_all("a")
    
                        if not len(links):
                            continue
        
                        finishedURLs = []
    
                        for anchor in links:
                            if time.time() > debugTime + WARN_TIME and not warned:
                                log.warn("Spent over {} seconds on post (ID: {})".format(
                                    WARN_TIME, submission.name))
        
                                warned = True
        
                            log.debug("Found link in text post...")
        
                            fixedurl = fix_url(anchor['href'])
        
                            if skip_url(fixedurl):
                                continue
        
                            if fixedurl in finishedURLs:
                                continue #skip for sanity
        
                            archives.append(ArchiveContainer(fixedurl, anchor.contents[0]))
                            finishedURLs.append(fixedurl)
                            ratelimit(fixedurl)
                            wait=5 #resets error wait time.
                            
                    else: #for text posts with no content
                        skipped = 2
                        log.info("Skipped")                            
                else:
                    skipped = 2
                    log.info("Skipped")
                    
                if skipped == 1 :
                    Notification(submission, archives, submission.url).notify()
                    log.info("Reply sent")
                    time.sleep(20)
                    skipped = 0

if __name__ == "__main__":
    outlinebot = OutlineBot()
    log.info("Started.")
    try:
        while True:
            try:
                log.info("Running")
                outlinebot.run()
                log.info("Done")
            except RECOVERABLE_EXC as e:
                log.error(e)
                if wait >= 160:
                    log.error("Error: Waiting {} seconds before trying again. If errors continue, check your internet connection and bot's username and password".format(wait))
                else:
                    log.error("Error: Waiting {} seconds before trying again.".format(wait))
                wait = err_wait(wait)                
    except KeyboardInterrupt:
        log.info("Stop Dave. I'm afraid.")
        pass
    exit(0)