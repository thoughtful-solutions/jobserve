# JobServe CLI Scraper Setup

## Requirements

Create a `requirements.txt` file:

```
scrapy>=2.11.0
lxml>=4.9.0
twisted>=22.10.0
```

## Installation

1. **Create a virtual environment (recommended):**
   ```bash
   python -m venv jobserve_env
   source jobserve_env/bin/activate  # On Windows: jobserve_env\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Make the script executable:**
   ```bash
   chmod +x jobserve_scraper.py
   ```

## Usage

### Basic Usage
```bash
python jobserve_scraper.py "python developer" --location "London"
```

### Advanced Usage
```bash
# Search for data scientist jobs in Manchester within 20 miles, posted in last 14 days
python jobserve_scraper.py "data scientist" --location "Manchester" --miles 20 --days 14

# Limit results to top 25 jobs
python jobserve_scraper.py "python developer" --location "London" --limit 25

# Quick search for just the top 10 most recent jobs
python jobserve_scraper.py "DevOps engineer" --location "Birmingham" --limit 10 --days 3

# With login credentials
python jobserve_scraper.py "software engineer" --location "Birmingham" --username your_username --password your_password

# Enable verbose logging
python jobserve_scraper.py "DevOps engineer" --location "Leeds" --verbose
```

### Command Line Arguments

- `keywords` (required): Job search keywords
- `--location, -l` (required): Location to search around
- `--days, -d`: Number of days to search within (default: 7)
- `--miles, -m`: Search radius in miles (default: 10)
- `--limit, -n`: Maximum number of jobs to retrieve (default: no limit)
- `--username, -u`: JobServe username (optional)
- `--password, -p`: JobServe password (optional)
- `--output, -o`: Output results to JSON file (optional)
- `--debug`: Enable debug mode (saves HTML pages for inspection)
- `--verbose, -v`: Enable verbose logging

## Features

✅ **Command-line interface** with argparse  
✅ **Job result limiting** - specify maximum number of jobs to retrieve  
✅ **Login support** (optional) for accessing more features  
✅ **Configurable search parameters** (keywords, location, radius, days)  
✅ **Date-ordered results** (newest first)  
✅ **Respectful scraping** with delays and proper headers  
✅ **Error handling** and logging  
✅ **Clean output format** with job details  
✅ **Debug mode** for troubleshooting  

## Output Format

The tool displays jobs in the following format:
```
=== Found 10 jobs (limited to 10) ===

1. Senior Python Developer
   Company: Tech Corp Ltd
   Location: London
   Salary: £50,000 - £70,000
   Posted: 2025-06-29
   URL: https://jobserve.com/gb/en/...
--------------------------------------------------
2. Python Developer
   Company: StartUp Inc
   Location: London
   Salary: £45,000 - £60,000
   Posted: 2025-06-28
   URL: https://jobserve.com/gb/en/...
--------------------------------------------------

Note: Results limited to 10 jobs. Use --limit to change or remove limit.
```

## Important Notes

1. **Respect the website**: The tool includes delays between requests to be respectful to JobServe's servers.

2. **Job limiting**: Use `--limit` to control how many jobs you retrieve:
   - Faster searches when you only need a few recent jobs
   - Reduces load on JobServe's servers
   - Stops pagination early once limit is reached
   - Results are sorted by date (newest first) before limiting

3. **Website structure**: JobServe may change their HTML structure. If the scraper stops working, you may need to update the CSS selectors in the `extract_job_data` method.

4. **Login benefits**: Some job sites show more results or details to logged-in users. Provide credentials if you have an account.

5. **Rate limiting**: If you get blocked, increase the `DOWNLOAD_DELAY` in the settings.

## Troubleshooting

### Common Issues:

1. **No jobs found**: 
   - Check if the selectors need updating
   - Try with verbose logging to see what's happening
   - Verify the search criteria aren't too restrictive

2. **Login fails**:
   - Verify your credentials
   - Check if the login form structure has changed

3. **Connection errors**:
   - Check your internet connection
   - JobServe might be temporarily down
   - You might be rate-limited (wait and try again)

### Updating Selectors

If JobServe changes their HTML structure, you may need to update the CSS selectors in the `extract_job_data` method. Use browser developer tools to inspect the job listing elements and update accordingly.

## Legal Considerations

- This tool is for personal use and educational purposes
- Ensure you comply with JobServe's Terms of Service
- Don't abuse the service with excessive requests
- Respect robots.txt if required
