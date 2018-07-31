#!/usr/bin/python3

contact_info = "" #Your username or subreddit name, with /u/ or /r/ included. Needed so users can contact you. If a sub name is used, modmail will be sent to that sub.
working_sub = "" #The sub you want the bot to run in.
bot_UN = "" #The bot's username. Should be the same as the name in brackets in your praw.ini file (e.g. [OutlineBot1]).
footer_text = "I am a bot for archiving links." #This text is meant to explain the purpose of the bot.
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
USER_AGENT = "Creates archives links for linked websites. Contact me at Reddit.com at {}".format(contact_info)
ARCHIVE_ORG_FORMAT = "%Y%m%d%H%M%S"
MEGALODON_JP_FORMAT = "%Y-%m%d-%H%M-%S"
LEN_MAX = 35
REDDIT_API_WAIT = 10
WARN_TIME = 300 #warn after spending 5 minutes on a post
REDDIT_PATTERN = re.compile("https?://(([A-z]{2})(-[A-z]{2})"
                            "?|beta|i|m|pay|ssl|www)\.?reddit\.com")
SUBREDDIT_OR_USER = re.compile("/(u|user|r)/[^\/]+/?$")

reddit = praw.Reddit(bot_UN, user_agent=USER_AGENT)
ignorelist = set()

RECOVERABLE_EXC = (APIException,
                   ClientException,
                   ResponseException,
                   RequestException,
                   OAuthException)
                   

loglevel = logging.DEBUG if os.environ.get("DEBUG") == "true" else logging.INFO

logging.basicConfig(level=loglevel, format="[%(asctime)s] [%(levelname)s] %(message)s")

log = logging.getLogger("snapshill")
logging.getLogger("requests").setLevel(loglevel)
warnings.simplefilter("ignore")  # Ignore ResourceWarnings (because screw them)



if not os.path.isfile("{}_posts_replied_to.txt".format(working_sub)):
    posts_replied_to = []

# If we have run the code before, load the list of posts we have replied to
else:
    # Read the file into a list and remove any empty values
        with open("{}_posts_replied_to.txt".format(working_sub), "r") as f:
            posts_replied_to = f.read()
            posts_replied_to = posts_replied_to.split("\n")
            posts_replied_to = list(filter(None, posts_replied_to))
            
#If a quote file does not exist, do not include quotes. Otherwise, read quotes from file into list for later use.
if not os.path.isfile("{SUB}_quotes.txt".format(SUB=working_sub)):
    log.warn("There is no file for quotes. If you want quotes, create a file called {}_quotes.txt. Refer to the README for more detailed instructions on building the quote file.".format(working_sub))
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
        fixedurl = "http://www.reddit.com" + url
        log.info("fixedurl: "+url)
        return fixedurl
    else:
        log.info("unfixedurl: "+url)
        return url

def skip_url(url):
    """
    Skip naked username mentions and subreddit links.
    """
    if REDDIT_PATTERN.match(url) and SUBREDDIT_OR_USER.search(url):
        return True

    return False

def err_wait():
    if wait >= 160: #Caps the error wait time at 160 seconds.
        wait = 160
        log.error("Error: Waiting {} seconds".format(wait))
        time.sleep(wait)
    else:
        wait = wait*2 #Exponential backoff when there is an error.
        log.error("Error: Waiting {} seconds".format(wait))
        time.sleep(wait)

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
			
class ArchiveIsArchive(NameMixin):
    site_name = "archive.is"

    def __init__(self, url):
        self.url = url
        self.archived = self.archive()
        pairs = {"url": self.url, "run": 1}
        self.error_link = "https://archive.is/?{}".format(urlencode(pairs))

    def archive(self):
        """
        Archives to archive.is. Returns a 200, and we have to find the
        JavaScript redirect through a regex in the response text.
        :return: URL of the archive or False if an error occurred
        """
        pairs = {"url": self.url}
        attempts = 0
        try:
            res = requests.post("https://archive.is/submit/", pairs, verify=False) #Submits url to archive.is
        except RECOVERABLE_EXC:
            if attempts > 4:
                return "https://i.imgur.com/GVmRi8J.jpg"
            else:
                attempts += 1
                err_wait()
        log.debug(pairs)
        AIS_link = "http://archive.is/newest/{}".format(self.url) 
        log.debug(AIS_link)
        if len(AIS_link) <= 25:
            return "https://i.imgur.com/GVmRi8J.jpg"
        return AIS_link
 

class ArchiveOrgArchive(NameMixin):
    site_name = "archive.org"

    def __init__(self, url):
        self.url = url
        self.archived = self.archive()
        self.error_link = "https://web.archive.org/save/" + self.url

    def archive(self):
        """
        Archives to archive.org. The website gives a 403 Forbidden when the
        archive cannot be generated (because it follows robots.txt rules)
        :return: URL of the archive, False if an error occurred, or None if
        we cannot archive this page.
        """
        attempts = 0
        try:
            requests.get("https://web.archive.org/save/" + self.url)
        except:
            attempts += 1
            if attempts > 4:
                return "https://i.imgur.com/GVmRi8J.jpg"
            else:
                err_wait()
         
        date = time.strftime(ARCHIVE_ORG_FORMAT, time.gmtime())
        log.info("https://web.archive.org/{DATE}/{URL}".format(DATE=date,URL=self.url))
        return "https://web.archive.org/{DATE}/{URL}".format(DATE=date,URL=self.url)


class RemovedditArchive(NameMixin):
    site_name = "removeddit.com"

    def __init__(self, url):
        self.url = url
        self.archived = re.sub(REDDIT_PATTERN, "https://www.removeddit.com", url)
        self.error_link = "https://www.removeddit.com/"
        return self.archived

class ArchiveContainer:
    def __init__(self, url, text):
        log.debug("Creating ArchiveContainer")
        self.url = url
        self.text = (text[:LEN_MAX] + "...") if len(text) > LEN_MAX else text
        self.archives = [ArchiveOrgArchive(url)]

        if re.match(REDDIT_PATTERN, url):
            self.archives.append(RemovedditArchive(url))

        self.archives.append(ArchiveIsArchive(url))

def get_footer():
    return "*{ftr_text}* [^(*github*)](https://github.com/LightUmbra/Reddit-archive-bots) ^/ [*Contact for info or issues*]({contact})".format(ftr_text=footer_text, contact=CONTACT)

class Notification:

    def __init__(self, post, links):
        self.post = post
        self.links = links

    def notify(self):
        """
        Replies with a comment containing the archives or if there are too
        many links to fit in a comment, post a submisssion to
        /r/SnapshillBotEx and then make a comment linking to it.
        :return Nothing
        """
        try:
            comment = self._build()
            if len(comment) > 9999:
                comment = self.post.reply("There are too many links for me to handle and my creator was too lazy to make a sub to handle this.")
                log.info("Posted a comment and new submission")
            else:
                comment = self.post.reply(comment)
        except RECOVERABLE_EXC as e:
            log_error(e)
            return
        

    def _build(self):
        quote = random.choice(quotes)
        log.info(quote) 
        parts =  ["{}".format(quote), "Snapshots:"]
        format = "[{name}]({archive})"

        for i, link in enumerate(self.links, 1):
            subparts = []
            log.debug("Found link")

            for archive in link.archives:
                if archive.archived is None:
                    continue

                archive_link = archive.archived

                if not archive_link:
                    log.debug("Not found, using error link")
                    archive_link = archive.error_link + ' "could not ' \
                                                        'auto-archive; ' \
                                                        'click to resubmit it!"'
                else:
                    log.debug("Found archive")

                subparts.append(format.format(name=archive.name,
                                              archive=archive_link))

            parts.append("{}. {} - {}".format(i, link.text, ", ".join(subparts)))

        parts.append(get_footer())

        return "\n\n".join(parts)


class Snapshill:

    def __init__(self):
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
                with open("drama_posts_replied_to.txt", "a") as posts:
                    posts.write("{}\n".format(submission.id))
                    posts.close()
                log.info("Found submission.: {}".format(submission.permalink))

                archives = [ArchiveContainer(fix_url(submission.url),"*This Post*")]
                if submission.is_self and submission.selftext_html is not None:
                    log.debug("Found text post...")

                    links = BeautifulSoup(unescape(
                        submission.selftext_html)).find_all("a")

                    if not len(links):
                        continue

                    finishedURLs = []

                    for anchor in links:
                        if time.time() > debugTime + WARN_TIME and not warned:
                            log.warn("Spent over {} seconds on post (ID: {})".format(WARN_TIME, submission.name))
                            warned = True

                        log.debug("Found link in text post...")

                        url = fix_url(anchor['href'])

                        if skip_url(url):
                            continue

                        if url in finishedURLs:
                            continue #skip for sanity

                        archives.append(ArchiveContainer(url, anchor.contents[0]))
                        finishedURLs.append(url)
                        ratelimit(url)
                        time.sleep(50)

                Notification(submission, archives).notify()
                time.sleep(12)


if __name__ == "__main__":
    wait = 5
    log.info("Starting...")
    snapshill = Snapshill()

    log.info("Started.")
    try:
        while True:
            try:
                cycles += 1
                log.info("Running")
                snapshill.run()
                log.info("Done")

            except RECOVERABLE_EXC as e:
                log_error(e)
                err_wait()
    except KeyboardInterrupt:
        pass
    exit(0)

