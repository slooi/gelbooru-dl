import asyncio
import logging
import math
from typing import Callable, Dict, List, Tuple, TypedDict
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
from rich.progress import Progress, TaskID
from rich.console import Console
from requests.models import Response
import aiohttp
import time


# ----- USER CONFIGURABLE SETTINGS ----------------------------------------

ROOT_SAVE_DIRECTORY:pathlib.Path = pathlib.Path("IMGS3")
MAX_DL_ATTEMPTS = 7
DEFAULT_EXCLUDE_TAGS = "+-yaoi+-furry"
prepadding = "    "
MAX_CONCURRENT_REQUESTS = 8

# ----- LOGGING SETUP ----------------------------------------

logging.basicConfig(
	level=logging.INFO,
	format="%(message)s",
	handlers=[
		RichHandler(
			show_time=False,
			show_level=False,
			show_path=False,
			markup=True,
			rich_tracebacks=True,
			highlighter=NullHighlighter(),
		)
	]
)

log = logging.getLogger(__name__)

# ----- SETUP VARS ----------------------------------------

console = Console()
config = dotenv_values(".gelbooru-dl.env") 
API_CODES = config["API_CODES"]
custom_timeout = aiohttp.ClientTimeout(total=None, sock_read=60)

# ----- MAIN CODE ----------------------------------------


headers = {
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
}

s = sessions.Session()
s.headers.update(headers)

class DownloadInfo(TypedDict):
    url: str
    message: str
	
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
async def download_file(file_url:str,file_urls:List[str],media_save_folder:pathlib.Path,successful_urls:List[str],aborted_urls:List[str],already_downloaded_urls:List[str],currently_downloading_info:List[str],progress:Progress,task:TaskID,session:aiohttp.ClientSession):
	# cache
	num_of_file_urls = len(file_urls)
	indicator_width = len(str(num_of_file_urls))*2+1


	filepath = media_save_folder / pathlib.Path(file_url).name
	message = f"Downloading [steel_blue1]{file_url.replace("https://","")}[/steel_blue1] to [steel_blue1]{filepath.parent}[/steel_blue1]"

	def get_indicator():
			colored_fraction = f"[steel_blue1]{len(successful_urls)}[/steel_blue1]/[steel_blue1]{num_of_file_urls}[/steel_blue1]"
			percentage_done = f"([steel_blue1]{math.floor((len(successful_urls)+len(aborted_urls))/len(file_urls)*100)}%[/steel_blue1])"
			aborted_color = "steel_blue1" if len(aborted_urls)==0 else "red" 
			return (
				f"{colored_fraction} {percentage_done} downloaded"
				f" | [{aborted_color}]{len(aborted_urls)}[/{aborted_color}] aborted |"
			)
	def update_progress_bar_text():
		if len(currently_downloading_info)>0:
			progress.update(task, description=f"{prepadding}{get_indicator()} {currently_downloading_info[-1]}")
	is_dling = False

	async with semaphore:
		for download_attempt in range(1,MAX_DL_ATTEMPTS+1):
			part_filepath = None
			try:
				# SKIP FILE IF IT ALREADY EXISTS
				if filepath.exists():
					successful_urls.append(file_url)
					already_downloaded_urls.append(file_url)
					# progress.update(task, description=f"{prepadding}{get_indicator()} [cyan]Skipping (exists): {filepath}[/cyan]")
					# log.info(f"{get_indicator()} [steel_blue1]{filepath}[/steel_blue1] already exists. Skipping...")
					break

				# DOWNLOAD IF FILE DOESNT EXIST
				if not is_dling:
					is_dling = True
					currently_downloading_info.append(message)
				update_progress_bar_text()
				# progress.update(task, description=f"{prepadding}{get_indicator()} {message}")
				
				async with session.get(file_url,timeout=custom_timeout) as res:
					res.raise_for_status()

				# res = s.get(f"{file_url}")
				# res.raise_for_status()
					if not pathlib.Path(media_save_folder).exists(): os.makedirs(media_save_folder,exist_ok=True)


					# Download as a .part file first
					part_filepath = filepath.with_name(filepath.name + ".part")
					with open(part_filepath,"wb") as f:
						# 2. Increased chunk size to 64KB for better I/O performance
						async for chunk in res.content.iter_chunked(16777216):
							f.write(chunk)
					# 3. Rename the .part file to the final filename ONLY when 100% complete
					part_filepath.replace(filepath)

					successful_urls.append(file_url)
					update_progress_bar_text()
					# progress.update(task, description=f"{prepadding}{get_indicator()} Downloading [steel_blue1]{currently_downloading_info[-1]["url"].replace("https://","")}[/steel_blue1] to [steel_blue1]{filepath}[/steel_blue1]")

					await asyncio.sleep(.100)
					break
			except Exception as e:
				# Clean up .part file if it exists
				if part_filepath and part_filepath.exists():
					part_filepath.unlink() # Deletes the file
				
				if download_attempt == MAX_DL_ATTEMPTS:
					progress.print(f"{prepadding}[red]Download attempt {download_attempt}/{MAX_DL_ATTEMPTS} FAILED for {file_url}. ABORTING DOWNLOAD. Cause: {repr(e)}[/red]")
					aborted_urls.append(file_url)
				else:
					sleep_time = 1 + ((1+download_attempt) ** 2)
					progress.print(f"{prepadding}[yellow]Download attempt {download_attempt}/{MAX_DL_ATTEMPTS} FAILED for {file_url}. Retrying download in {sleep_time:.1f}s...[/yellow]")
					await asyncio.sleep(sleep_time)

		if message in currently_downloading_info:
			currently_downloading_info.remove(message) # wait, is this even safe? when  usin async
		update_progress_bar_text()

		progress.advance(task, advance=1)	
	
async def download_files(file_urls:List[str],_media_save_folder:pathlib.Path,session:aiohttp.ClientSession):
	if len(file_urls) == 0:
		log.info(f"{prepadding}[yellow]⚠️  0 urls were found! Can not scrape media![/yellow]")
		return
	
	media_save_folder = pathlib.Path(_media_save_folder)

	# cache
	num_of_file_urls = len(file_urls)
	indicator_width = len(str(num_of_file_urls))*2+1

	successful_urls = []
	aborted_urls = []
	already_downloaded_urls = []
	currently_downloading_info:List[str] = []
	
	with Progress(console=console, transient=True) as progress:
		task = progress.add_task("[steel_blue1]Preparing downloads...", total=num_of_file_urls)
		
		
		atasks = [asyncio.create_task(download_file(
			file_url=file_url,
			file_urls=file_urls,
			media_save_folder=media_save_folder,
			
			successful_urls=successful_urls,
			aborted_urls=aborted_urls,
			already_downloaded_urls=already_downloaded_urls,
			currently_downloading_info=currently_downloading_info,
			progress=progress,
			task=task,
			session=session
		)) for i, file_url in enumerate(file_urls)]
		await asyncio.gather(*atasks)
			
	

	SUMMARY_MESSAGE = (
		f"{prepadding}"
		"{symbol}Downloaded [{color}]{successful_downloads_num}[/{color}]/[steel_blue1]{total_url_num}[/steel_blue1] files"
		"([steel_blue1]{new_downloads_num}[/steel_blue1] new, [steel_blue1]{already_downloaded_num}[/steel_blue1] already existed)."
		" [{color}]{aborted_num}[/{color}] files failed to download."
	)
	if len(aborted_urls) > 0: log.info(f"{prepadding}The following files failed to download:\n[red]{"\n".join([f"{prepadding*2}❌ {url}" for url in aborted_urls])}[/red]")
	log.info(SUMMARY_MESSAGE.format(
		symbol="✅ " if len(aborted_urls) == 0 else "⚠️  ",
		color="green" if len(aborted_urls) == 0 else "red",
		successful_downloads_num=len(successful_urls),
		total_url_num=len(file_urls),
		new_downloads_num=len(successful_urls)-len(already_downloaded_urls),
		already_downloaded_num=len(already_downloaded_urls),
		aborted_num=len(aborted_urls)
	))

async def get_posts_using_tags(tags:str,session:aiohttp.ClientSession) -> List[str]:
	if tags == "": raise Exception("ERROR: no tags given")

	FORMATABLE_URL = (
		"https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1"
		f"&{API_CODES}"
		"&tags={tags}"
		f"{DEFAULT_EXCLUDE_TAGS}"
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


			for attempt in range(1,MAX_DL_ATTEMPTS+1):
				try:
					async with session.get(FORMATABLE_URL.format(tags=tags,page_id=page_id),timeout=custom_timeout) as res:
						res.raise_for_status()

						# Parse Data
						data = await res.json()

						# Validate Data
						if "@attributes" not in data:
							raise Exception("ERROR: `@attributes` not in data")
						if "count" not in data["@attributes"]:
							raise Exception("ERROR: `count` not in data")
						if "post" not in data:
							if data["@attributes"]["count"] == 0:
								if page_id == 0:
									console.print(f"{prepadding}[red]🚨 Error no posts found. Are you sure the following tags exist: [bold]{tags}[/bold][/red]")
								else:
									console.print(f"{prepadding}[red]🚨 Error no post content found on page {page_id+1}. Stopping search and returning 0 urls. Are you sure your tags: [bold]{tags}[/bold] exists?[/red]")
								return file_urls
							raise Exception("ERROR: `post` not in data")

						# Extract Data
						urls = [post["file_url"] for post in data["post"]]
						file_urls.extend(urls)

						total_number_of_posts = int(data["@attributes"]["count"])

						break
				except Exception as e:
					if attempt == MAX_DL_ATTEMPTS:
						console.print(f"{prepadding}[red]Scraping attempt {attempt}/{MAX_DL_ATTEMPTS} FAILED for page {page_id+1}. Stopping search and returning {len(file_urls)} urls. Cause: {repr(e)}[/red]")
						return file_urls
						raise Exception("TODO")
					else:
						sleep_time = 1 + ((1+attempt) ** 2)
						# Update the status spinner to show the warning!
						console.print(f"{prepadding}[yellow]Scraping attempt {attempt}/{MAX_DL_ATTEMPTS} FAILED for page {page_id+1}. Retrying in {sleep_time}s...[/yellow]")
						await asyncio.sleep(sleep_time)
			
			# TERMINATION STATE
			# Gelbooru limits you to page_id 0 to 200
			if page_id==200:
				console.print(f"{prepadding}[yellow]Gathered Gelbooru limit of 20100 posts deep.[/yellow]")
				break
			# In case reach end and no urls are returned
			if len(urls) == 0:
				break
			# In case API returns different total_number_of_posts due to content being removed
			if total_number_of_posts is not None and len(file_urls) >= total_number_of_posts:
				break

			# Setup for next iteration
			page_id+=1
			await asyncio.sleep(0)

	return file_urls

searchs_to_download = [
]

async def main():
	async with aiohttp.ClientSession(headers=headers) as session:
		for i, search in enumerate(searchs_to_download):
			search = search.strip()
			log.info(f"[[steel_blue1]{i+1}[/steel_blue1]/[steel_blue1]{len(searchs_to_download)}[/steel_blue1]] [steel_blue1]{search}[/steel_blue1]")
			file_urls = await get_posts_using_tags(search,session=session)
			await download_files(file_urls=file_urls,_media_save_folder=ROOT_SAVE_DIRECTORY/search,session=session)
asyncio.run(main())