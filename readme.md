# Pre-requisites
1) Python (confirmed working on python 3.12)

# Steps
1) [Make a Gelbooru account](https://gelbooru.com/index.php?page=account&s=reg) (no email is required)
2) Go to [your account options](https://gelbooru.com/index.php?page=account&s=options) and enable "Display all site content"
3) Then scroll down and copy your `API Access Credentials`. It should look something like so: 
```
&api_key=a1239798a7a98d7a9d87ad98wn798a7dnaw987da9d8aw7d0a98nd7aw09d8wa7d0a9w8nd7aw908da7nd09a8dn7w90d8w7and98a7wnd98an7w79&user_id=2001235
```
4) Download the `gelbooru-dl.py` from this repo
5) Open your terminal an navigate to where you downloaded `gelbooru-dl.py`
6) Then run `python gelbooru-dl.py -k <API_ACCESS_CREDENTIALS>`. Replace `<API_ACCESS_CREDENTIALS>` with your `API Access Credentials` from step `3)`
6) Run `python gelbooru-dl.py <TAGS>` to download 
7) Images will be saved to the folder `gelbooru-dl/<TAGS>/`

Note: `<TAGS>` MUST be formatted following Gelbooru's URL tagging conventions. This means:
- Spaces are turned into underscores(`_`). Eg: `blue archive` => `blue_archive`
- Searches using two tags must use the plus(`+`) symbol.
    - Eg: To search for the tags `hololive` and `animal_ears` together, use: `hololive+animal_ears`

# Example Usage

```gelbooru-dl suzumiya_haruhi```

- This will download posts with the character tag `suzumiya_haruhi`

```gelbooru-dl wlop```
- This will download posts with the artist tag `wlop`

```gelbooru-dl suzumiya_haruhi+black_hair```
- This will only download posts containing BOTH `suzumiya_haruhi` and `black_hair` tags

```gelbooru-dl suzumiya_haruhi+black_hair nagato_yuki```
- This will only download posts containg BOTH `suzumiya_haruhi` and `black_hair` tags
- Then after the above is done, it will download posts with the `nagato_yuki` tag

```gelbooru-dl -l mylist.txt```
- This will download all the tags in `mylist.txt`
- In `mylist.txt` each seperate search must be indicated with either a space or new line.
- eg:
```
suzumiya_haruhi+black_hair nagato_yuki
wlop
```
- This will sequentially perform the 3 seperate searches in the order below:
    1) `suzumiya_haruhi+black_hair`
    2) `nagato_yuki`
    3) `wlop`