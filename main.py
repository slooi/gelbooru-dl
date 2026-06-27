import logging
from typing import List
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
# ----- USER CONFIGURABLE SETTINGS ----------------------------------------

ROOT_SAVE_DIRECTORY:pathlib.Path = pathlib.Path("IMAGES2")

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
	prepadding = "    "

	# log.info(f"Downloading to folder: \t[steel_blue1]{_image_save_folder}[/steel_blue1]")
	image_save_folder = pathlib.Path(_image_save_folder)

	# cache
	num_of_file_urls = len(file_urls)
	indicator_width = len(str(num_of_file_urls))*2+1

	successful_urls = []
	aborted_urls = []
	
	with Progress(console=console, transient=True) as progress:
		task = progress.add_task("[steel_blue1]Preparing downloads...", total=num_of_file_urls)
		
		for i, file_url in enumerate(file_urls):

			MAX_DOWNLOAD_ATTEMPTS = 5
			for download_attempt in range(1,MAX_DOWNLOAD_ATTEMPTS+1):
				try:
					# Skip download if file already exists
					filepath = image_save_folder / pathlib.Path(file_url).name
					process_text = f"[steel_blue1]{len(successful_urls)}[/steel_blue1]" f"/[steel_blue1]{num_of_file_urls}[/steel_blue1]"
					
					# 1. Create the colored fraction
					colored_fraction = f"[steel_blue1]{len(successful_urls)}[/steel_blue1]/[steel_blue1]{num_of_file_urls}[/steel_blue1]"
					# 2. Calculate how many characters it takes up on screen (without the color tags)
					visible_length = len(f"{len(successful_urls)}/{num_of_file_urls}")
					# 3. Create the exact amount of blank spaces needed to pad the right side
					padding_spaces = " " * (indicator_width - visible_length)
					
					aborted_color = "steel_blue1" if len(aborted_urls)==0 else"red" 
					process_indicator = (
						# f"job [steel_blue1]{i+1:>{indicator_width}}[/steel_blue1]"
						f"{colored_fraction}{padding_spaces} downloaded"
						f" | [{aborted_color}]{len(aborted_urls)}[/{aborted_color}] aborted |"
					)
					# (
					# 	f"job [steel_blue1]{i+1:>{indicator_width}}[/steel_blue1]" f"/[steel_blue1]{num_of_file_urls}[/steel_blue1]"
					# 	f" | [steel_blue1]{len(successful_urls):>{indicator_width}}[/steel_blue1] downloaded"
					# 	f" | [steel_blue1]{len(aborted_urls)}[/steel_blue1] aborted |"
					# )
					if filepath.exists():
						progress.update(task, description=f"{prepadding}{process_indicator} [cyan]Skipping (exists): {filepath}[/cyan]")
						# log.info(f"{process_indicator} [steel_blue1]{filepath}[/steel_blue1] already exists. Skipping...")
						successful_urls.append(file_url)
						break

					# Download if file doesn't already exist
					# Fetch
					# progress.update(task, description=f"[cyan]Downloading: {filepath.name}[/cyan]")
					progress.update(task, description=f"{prepadding}{process_indicator} Downloading [steel_blue1]{file_url}[/steel_blue1] to [steel_blue1]{filepath}[/steel_blue1]")
					# log.info(f"{process_indicator} Downloading [steel_blue1]{file_url}[/steel_blue1]\t to [steel_blue1]{filepath}[/steel_blue1]") # type: ignore
					res = s.get(f"{file_url}") #!@#!@#!@#!@#!@# undo later
					res.raise_for_status()
					# Download
					if not pathlib.Path(image_save_folder).exists(): os.makedirs(image_save_folder,exist_ok=True)
					with open(filepath,"wb") as f:
						f.write(res.content)
						successful_urls.append(file_url)
						time.sleep(.100)
						break
				except Exception as e:
					if download_attempt == MAX_DOWNLOAD_ATTEMPTS:
						progress.print(f"{prepadding}[red]Download attempt {download_attempt}/{MAX_DOWNLOAD_ATTEMPTS} FAILED for {file_url}. ABORTING DOWNLOAD. Info: {e}[/red]")
						# log.error(f"\n{prepadding}[red]Aborting download for {file_url}. Max download attempts of {MAX_DOWNLOAD_ATTEMPTS} reached. Info: {e}[/red]")
						aborted_urls.append(file_url)
					else:
						# log.warning(f"{prepadding}[yellow]Warning! Error occurred while attempting to download and save {file_url}. Info: {e}[/yellow]")
						sleep_time = 1+.250*download_attempt**3  #!@#!@#!@#!@#!@# undo later
						progress.print(f"{prepadding}[yellow]Download attempt {download_attempt}/{MAX_DOWNLOAD_ATTEMPTS} FAILED for {file_url}. Retrying download in {sleep_time:.1f}s...[/yellow]")
						# log.warning(f"\n{prepadding}[yellow]Download attempt {download_attempt}/{MAX_DOWNLOAD_ATTEMPTS} FAILED. Retrying download in {sleep_time:.1f}s...[/yellow]")
						time.sleep(sleep_time)
				
			progress.advance(task, advance=1)		
			
	
	if len(aborted_urls) == 0:
		log.info(f"{prepadding}✅ Successfully downloaded [green]{len(successful_urls)}[/green]/[steel_blue1]{len(file_urls)}[/steel_blue1] files. [green]{len(aborted_urls)}[/green] files failed to download.")
	else:
		log.info(f"{prepadding}The following files failed to download:\n[red]{"\n".join([f"{prepadding*2}❌ {url}" for url in aborted_urls])}[/red]")
		log.info(f"{prepadding}⚠️  Successfully downloaded [red]{len(successful_urls)}[/red]/[steel_blue1]{len(file_urls)}[/steel_blue1] files. [red]{len(aborted_urls)}[/red] files failed to download.")

	


def get_posts_using_tags(tags:str,debug=False) -> List[str]:
	FORMATABLE_URL = (
		"https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1"
		f"&{API_CODES}"
		"&tags={tags}"
		"&pid={page_id}"
	)

	if debug: log.info(f"Finding file urls...")
	# else: print(f"{prepadding}Finding file urls... ",end="")
	file_urls:List[str] = []

	page_id=0
	total_number_of_posts = ""
	
	while True:
		progress_indication = "" if total_number_of_posts == "" else f"{len(file_urls)}/{total_number_of_posts} file urls scraped. {total_number_of_posts-len(file_urls)} urls remaining. \t"
		log.debug(f"{progress_indication}Scraping page {page_id+1}...")
		
		try:
			response = s.get(FORMATABLE_URL.format(tags=tags,page_id=page_id))
			response.raise_for_status()

			str_data = response.text
			data = json.loads(str_data)
			
			urls:List[str] = [post["file_url"] for post in data["post"]]
			file_urls.extend(urls)

			# TERMINATION STATE
			total_number_of_posts = data["@attributes"]["count"]
			if len(file_urls) == total_number_of_posts:
				break

			# PREPARE FOR NEXT ITERATION
			page_id+=1
			time.sleep(.200)
		except Exception as e:
			if not debug:
				print("")
			raise Exception(e)

	if debug: log.info(f"[steel_blue1]{len(file_urls)}[/steel_blue1] file urls found")
	# else: print(f"[steel_blue1]{len(file_urls)}[/steel_blue1] found")
	
	return file_urls


prepadding = "    "


searchs_to_download = [
]
for i, search in enumerate(searchs_to_download):
	search = search.strip()
	# file_urls = get_posts()
	log.info(f"[steel_blue1]{i+1}[/steel_blue1]/[steel_blue1]{len(searchs_to_download)}[/steel_blue1] | Search: [steel_blue1]{search}[/steel_blue1]")
	with console.status(f"  Finding file urls..."):
		file_urls = get_posts_using_tags(search)
	download_file_urls(file_urls=file_urls,_image_save_folder=ROOT_SAVE_DIRECTORY/search)

""" 
MVP
1) Get all posts from artist
 - Log number of posts found
2) Get all full res image urls and download from posts
 - Log success: URL

"""

"""

Collect post urls number === count
"""



"""
Be able to download multiple artists at the same time as well as the tags
- able to see which comprehensive log of which artists and which specific urls failed to download and the ability to download them again. Perhaps the ability to download those specific files again

"""