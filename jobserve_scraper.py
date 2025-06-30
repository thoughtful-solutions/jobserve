#!/usr/bin/env python3
"""
JobServe CLI Scraper
A command-line tool to search jobs on JobServe.com using Scrapy
"""

import argparse
import sys
from datetime import datetime, timedelta
from urllib.parse import urljoin
import json
import re

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


class JobServeSpider(scrapy.Spider):
    name = 'jobserve'
    allowed_domains = ['jobserve.com']
    start_urls = ['https://jobserve.com/gb/en/JobListing.aspx']
    
    def __init__(self, keywords=None, days=7, miles=10, location=None, 
                 username=None, password=None, debug=False, limit=None, *args, **kwargs):
        super(JobServeSpider, self).__init__(*args, **kwargs)
        self.keywords = keywords or ""
        self.days = int(days)
        self.miles = int(miles)
        self.location = location or ""
        self.username = username
        self.password = password
        self.debug = debug
        self.limit = int(limit) if limit else None
        self.jobs = []
        
    async def start(self):
        """Start by visiting the main job listing page"""
        yield scrapy.Request(
            url=self.start_urls[0],
            callback=self.parse_login_page,
            meta={'dont_cache': True}
        )
    
    def parse_login_page(self, response):
        """Parse the initial page and handle login if credentials provided"""
        self.logger.info(f"Loaded page: {response.url}")
        
        if self.debug:
            with open('debug_login_page.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            self.logger.info("Saved login page to debug_login_page.html")
        
        # Check if login is needed
        login_form = response.css('form#frmLogin, form[action*="login"], form:contains("username"), form:contains("email")')
        
        if login_form and self.username and self.password:
            self.logger.info("Found login form, attempting to login...")
            # Extract form data for login
            form_data = {
                'txtUsername': self.username,
                'txtPassword': self.password,
            }
            
            # Try common username field names
            username_fields = ['txtUsername', 'username', 'email', 'login', 'user']
            password_fields = ['txtPassword', 'password', 'pass', 'pwd']
            
            for field in username_fields:
                if response.css(f'input[name="{field}"]'):
                    form_data[field] = self.username
                    
            for field in password_fields:
                if response.css(f'input[name="{field}"]'):
                    form_data[field] = self.password
            
            # Get any hidden form fields
            for hidden_input in login_form.css('input[type="hidden"]'):
                name = hidden_input.css('::attr(name)').get()
                value = hidden_input.css('::attr(value)').get()
                if name and value:
                    form_data[name] = value
            
            # Submit login form
            return scrapy.FormRequest.from_response(
                response,
                formdata=form_data,
                callback=self.after_login
            )
        else:
            if self.username and not login_form:
                self.logger.warning("Credentials provided but no login form found")
            # Proceed without login
            return self.perform_search(response)
    
    def after_login(self, response):
        """Handle response after login attempt"""
        # Check if login was successful
        if "login" in response.url.lower() and "error" in response.text.lower():
            self.logger.error("Login failed!")
            return
        
        self.logger.info("Login successful!")
        return self.perform_search(response)
    
    def perform_search(self, response):
        """Submit the job search form"""
        self.logger.info(f"Looking for search form on: {response.url}")
        
        # JobServe has a complex form structure, let's try a direct approach
        # We can construct a search URL or use the existing search dialog
        
        # First, let's try to use the search dialog that's on the page
        # JobServe shows a search form in the "searchdialog" div
        
        # Look for the search form fields in the page
        keyword_field = response.css('#txtKeyWords')
        location_field = response.css('#txtLocations')  
        
        if keyword_field and location_field:
            self.logger.info("Found search form fields on page")
            
            # Try to construct the form data for JobServe's search
            form_data = {}
            
            # Get all the form elements from the main form
            main_form = response.css('form[name="frm1"]')
            if main_form:
                # Get all hidden fields
                for hidden in main_form.css('input[type="hidden"]'):
                    name = hidden.css('::attr(name)').get()
                    value = hidden.css('::attr(value)').get()
                    if name and value:
                        form_data[name] = value
                
                # Set the search parameters
                form_data.update({
                    'ctl00$txtKeyWords': self.keywords,
                    'ctl00$txtLocations': self.location,
                    'selAge': str(self.days),
                    'selRad': str(self.miles),
                    'selInd': '00',  # All industries
                    'selJType': '15',  # Any job type
                    'ctl00$txtTitle': '',
                    'selClientType': '',
                    'selSal': '00',  # All salaries
                })
                
                # Try to trigger the search using the RunMainSearch action
                # This appears to be how JobServe handles search submission
                form_data['ctl00$RunMainSearch.x'] = '1'
                form_data['ctl00$RunMainSearch.y'] = '1'
                
                self.logger.info(f"Submitting search: keywords='{self.keywords}', location='{self.location}', days={self.days}, miles={self.miles}")
                
                return scrapy.FormRequest.from_response(
                    response,
                    formdata=form_data,
                    callback=self.parse_search_results,
                    method='POST'
                )
        
        # If the search form approach doesn't work, try a direct URL approach
        # JobServe might accept search parameters in the URL
        self.logger.warning("Could not find search form, trying direct URL approach")
        
        # Try constructing a search URL with parameters
        search_url = f"{response.url}?keywords={self.keywords}&location={self.location}&days={self.days}&radius={self.miles}"
        
        return scrapy.Request(
            url=search_url,
            callback=self.parse_search_results
        )
    
    def parse_search_results(self, response):
        """Parse the search results page"""
        self.logger.info(f"Parsing search results from: {response.url}")
        
        # Check if we've already reached our limit
        if self.limit and len(self.jobs) >= self.limit:
            self.logger.info(f"Job limit of {self.limit} reached. Stopping search.")
            return
        
        if self.debug:
            with open('debug_search_results.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            self.logger.info("Saved search results page to debug_search_results.html")
        
        # JobServe uses specific CSS classes for job listings
        job_listings = response.css('div.jobListItem')
        
        if job_listings:
            self.logger.info(f"Found {len(job_listings)} job listings using JobServe selectors")
        else:
            self.logger.warning("No job listings found with JobServe selectors")
            # Try alternative selectors as fallback
            job_listings = response.css('div[class*="jobListItem"], div[class*="job-item"], tr[class*="job"]')
            if job_listings:
                self.logger.info(f"Found {len(job_listings)} jobs using fallback selectors")
            else:
                self.logger.error("No jobs found with any selectors")
                return
            
        jobs_found = 0
        for job in job_listings:
            # Check if we've reached the limit before processing each job
            if self.limit and len(self.jobs) >= self.limit:
                self.logger.info(f"Reached job limit of {self.limit}. Stopping collection.")
                break
                
            job_data = self.extract_job_data(job, response)
            if job_data:
                self.jobs.append(job_data)
                jobs_found += 1
                
                # Log progress if we have a limit
                if self.limit:
                    remaining = self.limit - len(self.jobs)
                    self.logger.info(f"Collected {len(self.jobs)}/{self.limit} jobs ({remaining} remaining)")
        
        self.logger.info(f"Successfully extracted {jobs_found} jobs from this page")
        
        # Only continue pagination if we haven't reached the limit
        if not self.limit or len(self.jobs) < self.limit:
            # Look for next page links in JobServe's pagination
            next_page = response.css('span.nav_Next a::attr(href)').get()
            
            if next_page:
                remaining = self.limit - len(self.jobs) if self.limit else "unlimited"
                self.logger.info(f"Found next page: {next_page} (need {remaining} more jobs)")
                yield response.follow(next_page, callback=self.parse_search_results)
            else:
                self.logger.info("No more pages found")
        else:
            self.logger.info(f"Job limit of {self.limit} reached. Skipping pagination.")
    
    def extract_job_data(self, job_element, response):
        """Extract job data from a JobServe job listing element"""
        try:
            # Extract job title and URL using JobServe's specific structure
            title_element = job_element.css('a.jobListPosition')
            if not title_element:
                return None
                
            title = title_element.css('::text').get()
            job_url = title_element.css('::attr(href)').get()
            
            if not title or not title.strip():
                return None
            
            # Filter by keywords if we have them (case-insensitive)
            if self.keywords:
                keywords_lower = self.keywords.lower()
                title_lower = title.lower()
                
                # Check if any of the keywords appear in the job title
                keyword_words = keywords_lower.split()
                title_contains_keywords = any(keyword in title_lower for keyword in keyword_words)
                
                if not title_contains_keywords:
                    # Also check in job description if available
                    description_element = job_element.css('p.jobListSkills')
                    description = description_element.css('::text').get() if description_element else ""
                    
                    if description:
                        description_lower = description.lower()
                        description_contains_keywords = any(keyword in description_lower for keyword in keyword_words)
                        if not description_contains_keywords:
                            return None  # Skip jobs that don't match keywords
                    else:
                        return None  # Skip if no keywords match in title and no description
            
            # Extract job details using JobServe's specific structure
            # Location
            location_element = job_element.css('span#summlocation, span.jobListDetail[title*="UK"], span.jobListDetail[title*="London"], span.jobListDetail[title*=","]')
            location = "N/A"
            for loc_elem in location_element:
                loc_text = loc_elem.css('::text').get()
                if loc_text and ('UK' in loc_text or ',' in loc_text):
                    location = loc_text.strip()
                    break
            
            # Salary/Rate
            salary_element = job_element.css('span#summrate, span.jobListDetail[title*="£"], span.jobListDetail[title*="per"]')
            salary = "N/A"
            for sal_elem in salary_element:
                sal_text = sal_elem.css('::text').get()
                if sal_text and '£' in sal_text:
                    salary = sal_text.strip()
                    break
            
            # Job type
            type_element = job_element.css('span#summtype, span.jobListDetail')
            job_type = "N/A"
            for type_elem in type_element:
                type_text = type_elem.css('::text').get()
                if type_text and type_text.strip() in ['Permanent', 'Contract', 'Contract/Permanent', 'Part Time']:
                    job_type = type_text.strip()
                    break
            
            # Company - look for employment agency/company info
            company_element = job_element.css('span.jobListDetail a, a[title*="information about"], a[href*="Listings"]')
            company = "N/A"
            for comp_elem in company_element:
                comp_text = comp_elem.css('::text').get()
                if comp_text and comp_text.strip() and len(comp_text.strip()) > 2:
                    company = comp_text.strip()
                    break
            
            # Posted date
            date_element = job_element.css('span#summposteddate, span.jobListDetail[title*="/"]')
            date_text = "N/A"
            for date_elem in date_element:
                date_val = date_elem.css('::text').get()
                if date_val and ('/' in date_val or '2025' in date_val):
                    date_text = date_val.strip()
                    break
            
            posted_date = self.parse_date(date_text)
            
            # Clean up the data
            title = title.strip()
            location = location.strip() if location != "N/A" else "N/A"
            salary = salary.strip() if salary != "N/A" else "N/A"
            company = company.strip() if company != "N/A" else "N/A"
            
            # Create full URL for job
            if job_url:
                job_url = urljoin(response.url, job_url)
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'salary': salary,
                'type': job_type,
                'date': posted_date,
                'url': job_url,
                'posted_date_raw': date_text
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting job data: {e}")
            return None
    
    def get_text_from_selectors(self, element, selectors):
        """Try multiple selectors to get text content"""
        for selector in selectors:
            result = element.css(selector + '::text').get()
            if result and result.strip():
                return result.strip()
        return "N/A"
    
    def parse_date(self, date_text):
        """Parse date from various formats"""
        if not date_text:
            return datetime.now()
        
        date_text = date_text.strip().lower()
        
        try:
            # Handle "today", "yesterday", etc.
            if 'today' in date_text:
                return datetime.now()
            elif 'yesterday' in date_text:
                return datetime.now() - timedelta(days=1)
            elif 'days ago' in date_text or 'day ago' in date_text:
                days_match = re.search(r'(\d+)', date_text)
                if days_match:
                    days_ago = int(days_match.group(1))
                    return datetime.now() - timedelta(days=days_ago)
            
            # Try to parse standard date formats
            date_formats = [
                '%d/%m/%Y',
                '%d-%m-%Y', 
                '%Y-%m-%d',
                '%d %b %Y',
                '%d %B %Y'
            ]
            
            for date_format in date_formats:
                try:
                    return datetime.strptime(date_text, date_format)
                except ValueError:
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error parsing date '{date_text}': {e}")
        
        return datetime.now()
    
    def closed(self, reason):
        """Called when spider closes - sort and display results"""
        if self.jobs:
            # Sort jobs by date (newest first)
            self.jobs.sort(key=lambda x: x['date'], reverse=True)
            
            total_found = len(self.jobs)
            limit_text = f" (limited to {self.limit})" if self.limit and total_found >= self.limit else ""
            
            print(f"\n=== Found {total_found} jobs{limit_text} ===\n")
            
            for i, job in enumerate(self.jobs, 1):
                print(f"{i}. {job['title']}")
                print(f"   Company: {job['company']}")
                print(f"   Location: {job['location']}")
                print(f"   Type: {job.get('type', 'N/A')}")
                print(f"   Salary: {job['salary']}")
                print(f"   Posted: {job['date'].strftime('%Y-%m-%d')}")
                if job['url']:
                    print(f"   URL: {job['url']}")
                print("-" * 50)
                
            # Show summary
            if self.limit and total_found >= self.limit:
                print(f"\nNote: Results limited to {self.limit} jobs. Use --limit to change or remove limit.")
            else:
                print(f"\nTotal jobs found: {total_found}")
        else:
            search_params = f"'{self.keywords}' in {self.location}"
            if self.limit:
                search_params += f" (limit: {self.limit})"
            print(f"No jobs found matching your criteria: {search_params}")
            print("Try:")
            print("  - Using broader keywords")
            print("  - Increasing the search radius (--miles)")
            print("  - Increasing the time period (--days)")
            print("  - Using --debug --verbose to troubleshoot")


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description='Search for jobs on JobServe.com',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python jobserve_scraper.py "python developer" --location "London" --days 14 --miles 20
  python jobserve_scraper.py "data scientist" --location "Manchester" --username myuser --password mypass
  python jobserve_scraper.py "DevOps engineer" --location "Birmingham" --limit 25
  python jobserve_scraper.py "software engineer" --location "Leeds" --limit 10 --days 3
        """
    )
    
    parser.add_argument('keywords', 
                       help='Job search keywords')
    parser.add_argument('--location', '-l', 
                       required=True,
                       help='Location to search around')
    parser.add_argument('--days', '-d', 
                       type=int, 
                       default=7,
                       help='Number of days to search within (default: 7)')
    parser.add_argument('--miles', '-m', 
                       type=int, 
                       default=10,
                       help='Search radius in miles (default: 10)')
    parser.add_argument('--limit', '-n',
                       type=int,
                       help='Maximum number of jobs to retrieve (default: no limit)')
    parser.add_argument('--username', '-u',
                       help='JobServe username (optional)')
    parser.add_argument('--password', '-p',
                       help='JobServe password (optional)')
    parser.add_argument('--output', '-o',
                       help='Output results to JSON file')
    parser.add_argument('--debug',
                       action='store_true',
                       help='Enable debug mode (saves page content for inspection)')
    parser.add_argument('--verbose', '-v',
                       action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.keywords.strip():
        print("Error: Keywords cannot be empty")
        sys.exit(1)
    
    if not args.location.strip():
        print("Error: Location cannot be empty")
        sys.exit(1)
    
    # Configure Scrapy settings
    settings = get_project_settings()
    settings.setdict({
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'ROBOTSTXT_OBEY': False,  # May need to disable for some sites
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 2,  # Be respectful
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'COOKIES_ENABLED': True,
        'REDIRECT_ENABLED': True,
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 3,
        'LOG_LEVEL': 'INFO' if args.verbose else 'WARNING',
        'TELNETCONSOLE_ENABLED': False,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 1,
        'AUTOTHROTTLE_MAX_DELAY': 60,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
    })
    
    # Create and configure the crawler process
    process = CrawlerProcess(settings)
    
    # Add the spider with arguments
    process.crawl(
        JobServeSpider,
        keywords=args.keywords,
        days=args.days,
        miles=args.miles,
        location=args.location,
        username=args.username,
        password=args.password,
        debug=args.debug,
        limit=args.limit
    )
    
    print(f"Searching JobServe for '{args.keywords}' jobs...")
    print(f"Location: {args.location} (within {args.miles} miles)")
    print(f"Posted within: {args.days} days")
    if args.limit:
        print(f"Result limit: {args.limit} jobs")
    if args.username:
        print("Using login credentials")
    else:
        print("Searching without login (use --username and --password for potentially more results)")
    print("-" * 50)
    
    # Start the crawler
    try:
        process.start()
    except KeyboardInterrupt:
        print("\nSearch interrupted by user")
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
