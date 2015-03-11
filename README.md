# CREST-Market-Downloader
Python (wx python) based market downloader. Downloads all orders in a region.


Requires:
* python 2.something
* wx python
* requests

You need to set up your own application in the developers site, and fill in details into downloader.ini appropriately.

The callback url on the developers site is http://localhost:[port from downloader.ini]/

My first wx program, so probably hideously inefficient


Dumps all orders (well, as long as there's less than 1000 buy or sell for each item) in a region into orders.csv

Takes around 15 minutes to process. I need to work in some kind of limiter, because most people won't want everything.

Now also needs a cacert.pem file in the same directory as the script. In part, so it packages nicely with pyinstaller.

https://www.fuzzwork.co.uk/resources/CrestDownloader.zip for a packaged version, just configure the downloader.ini
