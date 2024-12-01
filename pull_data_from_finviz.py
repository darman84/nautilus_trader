import scrapy
from scrapy.crawler import CrawlerProcess

class FinvizSpider(scrapy.Spider):
    name = "finviz_spider"
    
    # The URL with your specific filters
    start_urls = ['https://finviz.com/screener.ashx?v=111&f=geo_usa,sh_avgvol_o300,sh_opt_option,sh_short_low,ta_beta_u2&ft=4&o=-volume']

    def parse(self, response):
        # Modified XPath to capture all tickers including the first one
        tickers = response.xpath('//table[@id="screener-views-table"]//tr/td[2]/a/text()').getall()
        
        # Print each ticker
        for ticker in tickers:
            print(ticker)

# Set up the crawler process
process = CrawlerProcess({
    'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'ROBOTSTXT_OBEY': False
})

# Run the spider
process.crawl(FinvizSpider)
process.start()
