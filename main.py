import logging
from typing import Callable, List
from bs4 import BeautifulSoup
from requests import sessions
import json
from dotenv import dotenv_values
import time
import pathlib
import os
from rich.highlighter import NullHighlighter
from rich.logging import RichHandler
from rich import print
from rich.progress import Progress
from rich.console import Console
from requests.models import Response
# ----- USER CONFIGURABLE SETTINGS ----------------------------------------

ROOT_SAVE_DIRECTORY:pathlib.Path = pathlib.Path("IMAGES2")
MAX_RETRY_ATTEMPTS = 5
prepadding = "    "


# ----- LOGGING SETUP ----------------------------------------

logging.basicConfig(
	level=logging.INFO,
	# format="%(asctime)s [%(levelname)s] %(message)s",
	# format="%(asctime)s [%(levelname)s] %(message)s",
	format="%(message)s",   # IMPORTANT: kills INFO:__name__ etc
	handlers=[
		RichHandler(
			show_time=False,
			show_level=False,
			show_path=False,
			markup=True,
			rich_tracebacks=True,
			highlighter=NullHighlighter(),
		)
		# logging.FileHandler("download.log", encoding="utf-8"),
		# logging.StreamHandler()  # still prints to console too
	]
)

log = logging.getLogger(__name__)

# ----- SETUP VARS ----------------------------------------

console = Console()
config = dotenv_values(".gelbooru-dl.env") 
API_CODES = config["API_CODES"]

# ----- MAIN CODE ----------------------------------------

s = sessions.Session()
s.headers.update({
	"Host": "img4.gelbooru.com",
	"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
	"Accept": "image/avif,image/webp,image/png,image/svg+xml,image/*;q=0.8,*/*;q=0.5",
	"Accept-Language": "en-US,en;q=0.9",
	"Accept-Encoding": "gzip, deflate, br, zstd",
	"Connection": "keep-alive",
	"Referer": "https://gelbooru.com/",
	"Sec-Fetch-Dest": "image",
	"Sec-Fetch-Mode": "no-cors",
	"Sec-Fetch-Site": "same-site",
	"Priority": "u=5, i",
	"Pragma": "no-cache",
	"Cache-Control": "no-cache"
})


def download_file_urls(file_urls:List[str],_image_save_folder:pathlib.Path):
	image_save_folder = pathlib.Path(_image_save_folder)

	# cache
	num_of_file_urls = len(file_urls)
	indicator_width = len(str(num_of_file_urls))*2+1

	successful_urls = []
	aborted_urls = []
	already_downloaded_urls = []
	
	with Progress(console=console, transient=True) as progress:
		task = progress.add_task("[steel_blue1]Preparing downloads...", total=num_of_file_urls)
		
		for i, file_url in enumerate(file_urls):
			filepath = image_save_folder / pathlib.Path(file_url).name

			# CALCULATE UI VARIABLES
			colored_fraction = f"[steel_blue1]{len(successful_urls)}[/steel_blue1]/[steel_blue1]{num_of_file_urls}[/steel_blue1]"
			visible_length = len(f"{len(successful_urls)}/{num_of_file_urls}")
			padding_spaces = " " * (indicator_width - visible_length)
			aborted_color = "steel_blue1" if len(aborted_urls)==0 else"red" 
			process_indicator = (
				f"{colored_fraction}{padding_spaces} downloaded"
				f" | [{aborted_color}]{len(aborted_urls)}[/{aborted_color}] aborted |"
			)

			for download_attempt in range(1,MAX_RETRY_ATTEMPTS+1):
				try:
					# SKIP FILE IF IT ALREADY EXISTS
					if filepath.exists():
						progress.update(task, description=f"{prepadding}{process_indicator} [cyan]Skipping (exists): {filepath}[/cyan]")
						# log.info(f"{process_indicator} [steel_blue1]{filepath}[/steel_blue1] already exists. Skipping...")
						successful_urls.append(file_url)
						already_downloaded_urls.append(file_url)
						break

					# DOWNLOAD IF FILE DOESNT EXIST
					progress.update(task, description=f"{prepadding}{process_indicator} Downloading [steel_blue1]{file_url.replace("https://","")}[/steel_blue1] to [steel_blue1]{filepath}[/steel_blue1]")
					res = s.get(f"{file_url}")
					res.raise_for_status()
					if not pathlib.Path(image_save_folder).exists(): os.makedirs(image_save_folder,exist_ok=True)
					with open(filepath,"wb") as f:
						f.write(res.content)
						successful_urls.append(file_url)
						time.sleep(.100)
						break
				except Exception as e:
					if download_attempt == MAX_RETRY_ATTEMPTS:
						progress.print(f"{prepadding}[red]Download attempt {download_attempt}/{MAX_RETRY_ATTEMPTS} FAILED for {file_url}. ABORTING DOWNLOAD. Info: {e}[/red]")
						aborted_urls.append(file_url)
					else:
						sleep_time = 1 + (.25*download_attempt**3)
						progress.print(f"{prepadding}[yellow]Download attempt {download_attempt}/{MAX_RETRY_ATTEMPTS} FAILED for {file_url}. Retrying download in {sleep_time:.1f}s...[/yellow]")
						time.sleep(sleep_time)
				
			progress.advance(task, advance=1)		
			
	
	if len(aborted_urls) == 0:
		log.info(f"{prepadding}✅ Successfully downloaded [green]{len(successful_urls)}[/green]/[steel_blue1]{len(file_urls)}[/steel_blue1] files. [green]{len(aborted_urls)}[/green] files failed to download. [steel_blue1]{len(already_downloaded_urls)}[/steel_blue1] files were already downloaded")
	else:
		log.info(f"{prepadding}The following files failed to download:\n[red]{"\n".join([f"{prepadding*2}❌ {url}" for url in aborted_urls])}[/red]")
		log.info(f"{prepadding}⚠️  Successfully downloaded [red]{len(successful_urls)}[/red]/[steel_blue1]{len(file_urls)}[/steel_blue1] files. [red]{len(aborted_urls)}[/red] files failed to download. [steel_blue1]{len(already_downloaded_urls)}[/steel_blue1] files were already downloaded")


# def safe_request(url:str,success_cb:Callable[[Response]],max_retries:int=MAX_RETRY_ATTEMPTS):
# 	for attempt in range(1,max_retries+1):
# 		try:
# 			response = s.get(url)
# 			response.raise_for_status()

			
# 		except Exception as e:
# 			if attempt == max_retries:

# 			else:


def get_posts_using_tags(tags:str) -> List[str]:
	FORMATABLE_URL = (
		"https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1"
		f"&{API_CODES}"
		"&tags={tags}"
		"&pid={page_id}"
	)
	file_urls:List[str] = []
	urls = []

	page_id=0
	total_number_of_posts = None
	with console.status(f"  Finding file urls...") as status:
		while True:
			# Indicate progress
			if not total_number_of_posts is None:
				warning_text = "[yellow]WARNING: Gelbooru prevents searches more than 20100 posts deep. Only the first 20100 posts will be scraped![/yellow]" if total_number_of_posts>=20100 else ""
				status.update(f"  Finding file urls... [steel_blue1]{len(file_urls)}[/steel_blue1]/[steel_blue1]{total_number_of_posts}[/steel_blue1] found. {warning_text}")


			for attempt in range(1,MAX_RETRY_ATTEMPTS+1):
				try:
					response = s.get(FORMATABLE_URL.format(tags=tags,page_id=page_id))
					response.raise_for_status()

					# Parse Data
					data = response.json()

					# Validate Data
					if "@attributes" not in data:
						raise Exception("ERROR: `@attributes` not in data")
						return file_urls 
					if "post" not in data:
						raise Exception("ERROR: `post` not in data")
						return file_urls 

					# Extract Data
					urls = [post["file_url"] for post in data["post"]]
					file_urls.extend(urls)

					total_number_of_posts = int(data["@attributes"]["count"])

					break
				except Exception as e:
					if attempt == MAX_RETRY_ATTEMPTS:
						log.error(f"  [red]Fatal error scraping page {page_id+1}. Stopping search and returning {len(file_urls)} urls. Cause: {e}[/red]")
						return file_urls
						raise Exception("TODO")
					else:
						sleep_time = 1 + (attempt * 3)
						# Update the status spinner to show the warning!
						status.update(f"  [yellow]Error on page {page_id+1}. Retrying {attempt}/{MAX_RETRY_ATTEMPTS} in {sleep_time}s...[/yellow]")
						time.sleep(sleep_time)
			
			# TERMINATION STATE
			# Gelbooru limits you to page_id 0 to 200
			if page_id==20000/100:
				console.print(f"{prepadding}[yellow]Reached Gelbooru limit of 20100 posts deep.[/yellow]")
				break
			# In case reach end and no urls are returned
			if len(urls) == 0:
				break
			# In case API returns different total_number_of_posts due to content being removed
			if total_number_of_posts is not None and len(file_urls) >= total_number_of_posts:
				break

			# Setup for next iteration
			page_id+=1
			time.sleep(.2)

	return file_urls

searchs_to_download = [
	"blue_archive+sort%3ascore"
]

for i, search in enumerate(searchs_to_download):
	search = search.strip()
	log.info(f"[steel_blue1]{i+1}[/steel_blue1]/[steel_blue1]{len(searchs_to_download)}[/steel_blue1] | Search: [steel_blue1]{search}[/steel_blue1]")
	file_urls = get_posts_using_tags(search)
	download_file_urls(file_urls=file_urls,_image_save_folder=ROOT_SAVE_DIRECTORY/search)