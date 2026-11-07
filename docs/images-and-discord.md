# Images and Discord

Two outputs draw each stockpile as an image, with the icon of each item:

- **image** saves the images as PNG files. It is the easy way to try how they look.
- **discord** posts them to a channel through a webhook.

Add them in **Settings → Output**. Each one has its own appearance settings, so two
outputs can show the same data differently.

## Appearance

| Setting | Default | Description |
|---------|---------|-------------|
| `headline` | what they share | Title of each image that merges stockpiles (`grouping`) |
| `language` | `en` | Language of the text of the image, which can differ from the one of the window |
| `icon_mod` | `vanilla` | Mod of the template database whose icons replace those of the base game |
| `font_path` | none | Font file tried before the fonts of the system |
| `grouping` | `none` | Which stockpiles of a send share an image: `none`, `all`, `hex` or `location` |

The `headline` and the Discord `message` accept these placeholders: `{name}`, `{type}`,
`{hex}`, `{ingame_timestamp}`, `{timestamp}`, `{resolution}`, `{item_count}`
and `{total_items}`.

A large stockpile is split into pages, each one a separate image.

**Title.** The image of a single stockpile shows its type and name, as the game does:
`Seaport - Public`, or the name of a reserve stockpile. Below it goes the hex.

**Icons** come from the database in `scanner.database_path`. Without a database, or for
an item the mod does not have, the image shows only the text.

**Text.** Names of stockpiles can be in any alphabet, as long as an installed font covers
it. If yours shows empty boxes, set `font_path` to a font that does.

**Language.** Each output has its own, so a channel can read the images in another language
than the window. Item names come from the game, which does not translate all of them, mostly
vehicles, and has no Spanish: those keep their English name. The rest of the text is
translated. In the `{type}` placeholder too.

**Grouping.** Each group of stockpiles is drawn as one, adding up their items:

| `grouping` | One image for | Named, without a `headline` |
|------------|---------------|-----------------------------|
| `none` | each stockpile | |
| `all` | the whole send | `All Stockpiles` |
| `hex` | each hex | the hex, such as `Heartlands` |
| `location` | each place, the stockpiles with the same coordinates, such as the public and reserve stockpiles of a seaport | its type, such as `Seaport` |

The `headline` names every merge, and its `{name}` is the name above. Stockpiles from
screenshots have no hex or coordinates, so `hex` and `location` leave them alone.

In a merge, crated and loose items stay apart. If the quantity of an
item could not be read in one of the stockpiles, its total shows `?`, because a number would
hide the stock that could not be read. A send with a single stockpile is drawn as it is,
with its own title.

## Image output

| Setting | Default | Description |
|---------|---------|-------------|
| `path` | `{timestamp}_{stockpile_name}.png` | Where to save each image. It accepts the placeholders of the [file output](configuration.md), and the extension is always `.png` |

## Discord output

Create the webhook in Discord, in the settings of the channel: **Integrations → Webhooks**.
Anyone with its URL can post to the channel, so treat it as a password. Foxhole Stockpiles
only sends it to Discord and does not write it to the log, but it is stored in your
configuration file.

| Setting | Default | Description |
|---------|---------|-------------|
| `url` | | URL of the webhook. Anything other than a Discord webhook is refused |
| `username` | name of the webhook | Name to post with |
| `avatar_url` | image of the webhook | Avatar to post with |
| `message` | none | Text posted with the images of each stockpile |
| `min_interval_minutes` | `0` | Minimum time between posts to this webhook, 0 for none |

```json
{
  "name": "Logistics channel",
  "handler": {
    "type": "discord",
    "url": "https://discord.com/api/webhooks/ID/TOKEN",
    "message": "{name} in {hex}",
    "grouping": "hex",
    "min_interval_minutes": 15
  }
}
```

Each stockpile is a message. Mentions in the text, such as `@everyone`, do not notify
anyone, because stockpile names are written by players.

### When something is not posted

Short rate limits are waited out. After any other failure, what was not posted goes again
with the next send, without repeating what already arrived. If it has newer data of the
same stockpile, only the newer data is posted.

During `min_interval_minutes` nothing is posted, and it works the same way: the data goes
with the first send after that time.

So nothing goes out on its own: **without another send, nothing is posted**. The data also
waits only in memory, which means that it is lost when the application closes, and that
the commands or actions that handle a single scan, such as `scan` on the command line or
scanning one save file from the window, do not keep it for the next one. They do report
in the log that it was not posted.
