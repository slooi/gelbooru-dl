import os
import sys
import logging
import asyncio
import aiohttp
import dotenv
import pathlib
import argparse
from typing import List
from dotenv import dotenv_values
from rich.highlighter import NullHighlighter
from rich.logging import RichHandler
from rich import print
from rich.console import Console
from rich.live import Live
from rich.console import Group
from rich.markup import escape
from rich.progress import (
	Progress, 
	TaskID, 
	TextColumn, 
	BarColumn, 
	TaskProgressColumn, 
	TimeRemainingColumn,
)
# ----- USER CONFIGURABLE SETTINGS ----------------------------------------

DEFAULT_ROOT_SAVE_DIRECTORY:pathlib.Path = pathlib.Path("gelbooru-dl")
MAX_DL_ATTEMPTS = 7
DEFAULT_EXCLUDE_TAGS = "+-yaoi+-furry"
PREPADDING = "    "
MAX_CONCURRENT_REQUESTS = 8
SUPPRESS_WARNINGS = False

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


# ----- CONSTANTS ----------------------------------------

HEADERS = {
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

# ----- SETUP VARS ----------------------------------------

API_CODES = "" #config["API_CODES"]
ENV_PATH = pathlib.Path.home() / ".gelbooru-dl.env"
console = Console()
custom_timeout = aiohttp.ClientTimeout(total=None, sock_read=1)


# ----- MAIN CODE ----------------------------------------

async def download_file(file_url:str,media_save_folder:pathlib.Path,successful_urls:List[str],aborted_urls:List[str],already_downloaded_urls:List[str],progress:Progress,main_task:TaskID,session:aiohttp.ClientSession,semaphore:asyncio.Semaphore):
	filepath = media_save_folder / pathlib.Path(file_url).name

	async with semaphore:
		file_task = None # Task for individual file progress
		for download_attempt in range(1,MAX_DL_ATTEMPTS+1):
			part_filepath = None
			try:
				# SKIP FILE IF IT ALREADY EXISTS
				if filepath.exists():
					successful_urls.append(file_url)
					already_downloaded_urls.append(file_url)
					break

				# DOWNLOAD IF FILE DOESNT EXIST				
				async with session.get(file_url,timeout=custom_timeout) as res:
					res.raise_for_status()

					# Create file_task with progress bar for this file
					if file_task is not None: progress.remove_task(file_task)
					file_size = int(res.headers.get('Content-Length', 0)) or None
					file_task = progress.add_task(
						f"{PREPADDING}  Downloading [steel_blue1]{file_url}[/steel_blue1]", 
						total=file_size
					)

					# Validate parent folder exists
					if not pathlib.Path(media_save_folder).exists(): os.makedirs(media_save_folder,exist_ok=True)

					# Download as a .part file first
					part_filepath = filepath.with_name(filepath.name + ".part")
					with open(part_filepath,"wb") as f:
						async for chunk in res.content.iter_chunked(1048576):
							f.write(chunk)
							# Update the byte progress!
							progress.update(file_task, advance=len(chunk))
					# Rename the .part file to the final filename ONLY when 100% complete
					part_filepath.replace(filepath)

					successful_urls.append(file_url)
					await asyncio.sleep(.100)
					break
			except Exception as e:
				# Clean up .part file if it exists
				if part_filepath and part_filepath.exists():
					try: 
						part_filepath.unlink() # Deletes the file
					except Exception as e2:
						if not SUPPRESS_WARNINGS: console.print(f"{PREPADDING}[yellow]COULD NOT DELETE TEMPORARY FILE: {filepath.name + ".part"}. Cause: {repr(e2)}[/yellow]")
				
				if download_attempt == MAX_DL_ATTEMPTS:
					console.print(f"{PREPADDING}[red]Download attempt {download_attempt}/{MAX_DL_ATTEMPTS} FAILED for {file_url}. ABORTING DOWNLOAD. Cause: {repr(e)}[/red]")
					aborted_urls.append(file_url)
				else:
					sleep_time = 1 + ((1+download_attempt) ** 2)
					if not SUPPRESS_WARNINGS: console.print(f"{PREPADDING}[yellow]Download attempt {download_attempt}/{MAX_DL_ATTEMPTS} FAILED for {file_url}. Retrying download in {sleep_time:.1f}s...[/yellow]")
					await asyncio.sleep(sleep_time)

		# Clean up progress bar after downloading/aborting file
		if file_task is not None:
			progress.remove_task(file_task)

		# Update the main overall progress bar text and advance it
		aborted_color = "steel_blue1" if len(aborted_urls) == 0 else "red"
		new_desc = (
			f"{PREPADDING} [steel_blue1]{len(successful_urls)}[/steel_blue1]/[steel_blue1]{progress.tasks[main_task].total}[/steel_blue1] downloaded | "
			f"[{aborted_color}]{len(aborted_urls)}[/{aborted_color}] aborted"
		)
		progress.update(main_task, description=new_desc, advance=1)
	
async def download_files(file_urls:List[str],_media_save_folder:pathlib.Path,session:aiohttp.ClientSession,semaphore:asyncio.Semaphore):
	if len(file_urls) == 0:
		if not SUPPRESS_WARNINGS: log.info(f"{PREPADDING}[yellow]⚠️  0 urls were found! Can not scrape media![/yellow]")
		return
	
	media_save_folder = pathlib.Path(_media_save_folder)

	# cache
	num_of_file_urls = len(file_urls)

	successful_urls = []
	aborted_urls = []
	already_downloaded_urls = []

	# Create a group for a header and progress bars
	header = f"{PREPADDING}Saving to: [steel_blue1]{media_save_folder}[/steel_blue1]"
	progress = Progress(
		TextColumn("[progress.description]{task.description}"),
		BarColumn(),
		TaskProgressColumn(),
		TimeRemainingColumn(),
	)
	render_group = Group(header, progress)
	
	# Live() instead of progress for rendering of multiple pieces of info. transient=True erases everything when done!
	with Live(render_group, console=console, transient=True):
		main_task = progress.add_task(f"{PREPADDING} 0/{num_of_file_urls} downloaded | 0 aborted", total=num_of_file_urls)
		
		atasks = [asyncio.create_task(download_file(
			file_url=file_url,
			media_save_folder=media_save_folder,
			
			successful_urls=successful_urls,
			aborted_urls=aborted_urls,
			already_downloaded_urls=already_downloaded_urls,
			progress=progress,
			main_task=main_task,
			session=session,
			semaphore=semaphore
		)) for i, file_url in enumerate(file_urls)]
		await asyncio.gather(*atasks)
	

	# DOWNLOAD FILES SUMMARY REPORT
	SUMMARY_MESSAGE = (
		f"{PREPADDING}"
		"{symbol}Downloaded [{color}]{successful_downloads_num}[/{color}]/[steel_blue1]{total_url_num}[/steel_blue1] files"
		"([steel_blue1]{new_downloads_num}[/steel_blue1] new, [steel_blue1]{already_downloaded_num}[/steel_blue1] already existed)."
		" [{color}]{aborted_num}[/{color}] files failed to download."
	)
	if len(aborted_urls) > 0: log.info(f"{PREPADDING}The following files failed to download:\n[red]{"\n".join([f"{PREPADDING*2}❌ {url}" for url in aborted_urls])}[/red]")
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
		"&limit=100"
	)
	file_urls:List[str] = []
	urls = []

	page_id=0
	total_number_of_posts = None
	has_given_warning = False
	with console.status(f"  Finding file urls...") as status:
		while True:
			# Indicate progress
			if not total_number_of_posts is None:
				if total_number_of_posts>=20100 and not has_given_warning:
					has_given_warning = True
					if not SUPPRESS_WARNINGS: console.print(f"{PREPADDING}[yellow]WARNING: Gelbooru API limits searches to a maximum of 20,100 results. Skipping {(total_number_of_posts-20100):,} posts (out of {total_number_of_posts:,} total matches).[/yellow]")
				if has_given_warning:
					status.update(f"  Finding file urls... [steel_blue1]{len(file_urls):,}[/steel_blue1]/[yellow]20,100[/yellow] found ([cyan]Total matches: {total_number_of_posts:,}[/cyan]).")
				else:
					status.update(f"  Finding file urls... [steel_blue1]{len(file_urls):,}[/steel_blue1]/[steel_blue1]{total_number_of_posts:,}[/steel_blue1] found.")


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
									console.print(f"{PREPADDING}[red]🚨 Error no posts found. Are you sure the following tags exist: [bold]{tags}[/bold][/red]")
								else:
									console.print(f"{PREPADDING}[red]🚨 Error no post content found on page {page_id+1}. Stopping search and returning 0 urls. Are you sure your tags: [bold]{tags}[/bold] exists?[/red]")
								return file_urls
							raise Exception("ERROR: `post` not in data")

						# Extract Data
						urls = [post["file_url"] for post in data["post"]]
						file_urls.extend(urls)

						total_number_of_posts = int(data["@attributes"]["count"])

						break
				except Exception as e:
					if attempt == MAX_DL_ATTEMPTS:
						console.print(f"{PREPADDING}[red]Scraping attempt {attempt}/{MAX_DL_ATTEMPTS} FAILED for page {page_id+1}. Stopping search and returning {len(file_urls)} urls. Cause: {repr(e)}[/red]")
						return file_urls
						raise Exception("TODO")
					else:
						sleep_time = 1 + ((1+attempt) ** 2)
						# Update the status spinner to show the warning!
						if not SUPPRESS_WARNINGS: console.print(f"{PREPADDING}[yellow]Scraping attempt {attempt}/{MAX_DL_ATTEMPTS} FAILED for page {page_id+1}. Retrying in {sleep_time}s...[/yellow]")
						await asyncio.sleep(sleep_time)
			
			# TERMINATION STATE
			# Gelbooru limits you to page_id 0 to 200
			if page_id==200:
				if not SUPPRESS_WARNINGS: console.print(f"{PREPADDING}[yellow]Gathered Gelbooru limit of 20100 posts deep.[/yellow]")
				break
			# In case reach end and no urls are returned
			if len(urls) == 0:
				break
			# In case API returns different total_number_of_posts due to content being removed
			if total_number_of_posts is not None and len(file_urls) >= total_number_of_posts:
				break

			# SETUP FOR NEXT ITERATION
			page_id+=1
			await asyncio.sleep(0)

	return file_urls

def remove_part_files(dir:pathlib.Path):
	if not dir.exists(): return

	# Collect .part files
	part_files = [*dir.glob("*.part")]
	if len(part_files) == 0: return

	log.info(f"{PREPADDING}[yellow]Found {len(part_files)} leftover .part files. Cleaning up...[/yellow]")
	for file_path in part_files:
		try:
			file_path.unlink()  # This deletes the file
		except Exception as e:
			log.warning(f"[warning]Failed to delete {file_path}. Skipping... Cause: {e}[/warning]")


# ----- CLI AND MAIN EXECUTION ----------------------------------------

async def main(searchs_to_download: List[str], save_dir: pathlib.Path, concurrent_requests:int):
	semaphore = asyncio.Semaphore(concurrent_requests)

	async with aiohttp.ClientSession(headers=HEADERS) as session:
		for i, search in enumerate(searchs_to_download):

			search = search.strip()
			log.info(f"[[steel_blue1]{i+1}[/steel_blue1]/[steel_blue1]{len(searchs_to_download)}[/steel_blue1]] [steel_blue1]{search}[/steel_blue1]")
			file_urls = await get_posts_using_tags(search,session=session)

			media_save_folder = save_dir/search
			await download_files(file_urls=file_urls,_media_save_folder=media_save_folder,session=session,semaphore=semaphore)
			remove_part_files(media_save_folder)

def cli_entry():
	"""This is the function triggered when you type 'gelbooru-dl' in the terminal."""
	global MAX_DL_ATTEMPTS
	global SUPPRESS_WARNINGS
	global API_CODES

	# 1. GATHER ARGUMENTS
	parser = argparse.ArgumentParser(description="Download images from Gelbooru using tags.")
	
	# MAIN ARGUMENTS - REQUIRED AT LEAST ONCE
	parser.add_argument("searches",nargs="+",help="Queries to search. Perform separate searches by adding a space between them (e.g. suzumiya_haruhi black_hair). Use '+' to search for posts with BOTH tags (e.g. suzumiya_haruhi+black_hair)")
	parser.add_argument("-k", "--key", default="", help="Your Gelbooru API credentials containing your api_key+user_id. YOU ARE REQUIRED TO RUN THIS AT LEAST ONCE")

	# AUXILIARY ARGUMENTS
	# Require inputs
	parser.add_argument("-d", "--save-dir", default=DEFAULT_ROOT_SAVE_DIRECTORY, help=f"Root save directory (default: {DEFAULT_ROOT_SAVE_DIRECTORY}. eg: Files will be saved into {DEFAULT_ROOT_SAVE_DIRECTORY/'<SEARCH>)'}")
	parser.add_argument("-c", "--concurrent-requests", default=MAX_CONCURRENT_REQUESTS, help=f"Max number of concurrent requests that can be made (default: {MAX_CONCURRENT_REQUESTS})")
	parser.add_argument("-m", "--max-retry-attempts", default=MAX_DL_ATTEMPTS-1, help=f"Number of retry attempts if something goes wrong file while downloading/saving a file. default: {MAX_DL_ATTEMPTS-1}")
	# Boolean flag
	parser.add_argument("-s", "--suppress-warnings", action='store_true', help=f"Suppress yellow warnings. It will suppress: warning popups if search can't download all posts due to Gelbooru 20100 post depth limit, downloading/scraping issues that are within retry limits, etc")

	args = parser.parse_args()


	# 2. PARSE ARGUMENTS
	# 2.1 PARSE MAIN ARGUMENTS
	# GET SERACHES
	searches = args.searches

	# SAVE/LOAD ENVIRONMENT VARIABLES
	key = str(args.key).strip()
	# Update/Add environment var if given
	if key:
		log.info(f"Saving credentials to : [steel_blue1]{ENV_PATH}[/steel_blue1]")
		if not ENV_PATH.exists(): ENV_PATH.touch()
		if len(key)<150: 
			if not SUPPRESS_WARNINGS: log.warning("[yellow]WARNING: Your credentials were shorter than expected, please double check you pasted your full API Access Credentials.[/yellow]")
		if not key[0] == "&": key="&"+key 
		if key: dotenv.set_key(ENV_PATH,"key",key)
	# Load env variables
	key = dotenv_values(ENV_PATH).get("key","")
	# Validate env variables are not None
	if not key:
		log.info(
			"\n[red]Missing [b]API CREDENTIALS[/b][/red]"
			"\n[b]How to add your credentials:[/b]"
			f"\n{PREPADDING}1. Log into your Gelbooru account in your web browser"
			f"\n{PREPADDING}2. Go to [steel_blue1]Settings -> Options[/steel_blue1] (or visit: [steel_blue1]https://gelbooru.com/index.php?page=account&s=options[/steel_blue1])"
			f"\n{PREPADDING}3. Scroll down to the very bottom. You should see [steel_blue1]API Access Credentials[/steel_blue1]"
			f"\n{PREPADDING}4. There will be a long string of text like shown below. Copy the whole thing"
			f"\n{PREPADDING}   [steel_blue1]&api_key=a1239798a7a98d7a9d87ad98wn798...(shortened for brevity's sake)...d09a8dn7w90d8w7and98a7wnd98an7w79&user_id=2001235 [/steel_blue1]"
			f"\n{PREPADDING}5. Now run [green bold]gelbooru-dl -k \"PASTE_YOUR_STRING_HERE\"[/green bold]. [b yellow]You must add DOUBLE QUOTES(\") to [b]BOTH SIDES[/b] of your string or it will fail![/b yellow]"
			f"\n{PREPADDING}Example: [green bold]gelbooru-dl -k \"&api_key=a1239798a7a98d7a9d87ad98wn798...(shortened for brevity's sake)...d09a8dn7w90d8w7and98a7wnd98an7w79&user_id=2001235\"[/green bold]"
		)
		sys.exit(1)
	API_CODES = key

	# 2.2 PARSE AUXILARY ARGUMENTS
	root_save_directory = pathlib.Path(args.save_dir)
	
	concurrent_requests = int(args.concurrent_requests)
	if not concurrent_requests>0: raise Exception("ERROR: `concurrent_requests` MUST be greater or equal to 1")

	max_dl_attempts = int(args.max_retry_attempts)+1
	MAX_DL_ATTEMPTS = max_dl_attempts
	SUPPRESS_WARNINGS = bool(args.suppress_warnings)

	safe_save_directory = escape(str(root_save_directory))
	console.print(( # MUST USE CONSOLE instead of log.info otherwise text like PUT GET, etc will be highlighted
		f"{"_"*((60-10)//2)} SETTINGS {"_"*((60-10)//2)} "
		f"\nSave directory: [steel_blue1]{safe_save_directory}[/steel_blue1]"
		f"\n{f'Concurrent requests: [steel_blue1]{concurrent_requests}[/steel_blue1]':<55}[i]<=increase this guy to dl faster by using [b]-c {escape("<amount>")}[/b]. but watch out, Gelbooru may throttle you which can cause some files to fail![/i]"
		f"\nRetry attempts: [steel_blue1]{max_dl_attempts-1}[/steel_blue1]"
		f"\n{f'Suppress warnings: [steel_blue1]{SUPPRESS_WARNINGS}[/steel_blue1]':<55}[i]<=like living on the edge? hide the yellow warnings by using the [b]-s[/b] flag![/i]"
		f"\n{"_"*60}"
	))

	try:
		asyncio.run(main(searches, root_save_directory,concurrent_requests))
	except KeyboardInterrupt:
		log.info("\n[red]Download cancelled by user[/red]")

if __name__ == "__main__":
	cli_entry()