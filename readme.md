# Pre-requisites
1) Python (confirmed working on python 3.12)

# Steps
1) [Make a Gelbooru account](https://gelbooru.com/index.php?page=account&s=reg) (no email is required)
2) Go to [your account options](https://gelbooru.com/index.php?page=account&s=options) and enable "Display all site content"
3) Then scroll down and copy your `API Access Credentials`. It should look something like so: 
```
&api_key=a1239798a7a98d7a9d87ad98wn798a7dnaw987da9d8aw7d0a98nd7aw09d8wa7d0a9w8nd7aw908da7nd09a8dn7w90d8w7and98a7wnd98an7w79&user_id=2001235
```
4) Open your terminal and install this repo by running `pip install gelbooru-dl`
5) Then run `gelbooru-dl -k <YOUR_API_ACCESS_CREDENTIALS>`. Replace `<YOUR_API_ACCESS_CREDENTIALS>` with your `API Access Credentials` from step `3)`
6) Run `gelbooru-dl <TAGS>` to download 
7) Images will be saved into a `./gelbooru-dl/<TAGS>/`. If the folder does not yet exist, it will be created

Note: `<TAGS>` MUST be formatted following Gelbooru's URL tagging conventions. This means:
- Spaces are turned into underscores(`_`). Eg: `blue archive` => `blue_archive`
- To search for two tags within the same search use the plus(`+`) symbol.
    - Eg: To search for the tags `animal_ears` and `hololive` together, use: `animal_ears+hololive`

# Example Usage

```gelbooru-dl suzumiya_haruhi```
- This will download posts with the character tag `suzumiya_haruhi`


```gelbooru-dl wlop```
- This will download posts with the artist tag `wlop`

```gelbooru-dl suzumiya_haruhi+black_hair```
- This will downloading posts with the tags `suzumiya_haruhi+black_hair`

```gelbooru-dl suzumiya_haruhi+black_hair nagato_yuki```
- This will downloading posts with the `suzumiya_haruhi+black_hair` tags
- Then after the above is done, it will download posts with the `nagato_yuki` tag