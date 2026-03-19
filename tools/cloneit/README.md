# CloneIt

Clone the demo site to create a new repoless AEM site with one click.

## What It Does

CloneIt creates a new repoless site by:

1. **Creating DA folder** – Creates the new site folder in DA with a minimal `index.html`.
2. **Copying DA content** – Recursively copies all files from the baseline DA site to the new site folder, skipping `drafts` and `demo-docs`. Uses the [DA List API](https://admin.da.live/list) to discover all files, then the [DA Copy API](https://opensource.adobe.com/da-admin/#tag/Copy) per file (the Copy API does not recurse into folders). If copy fails, falls back to updating the minimal `index.html`.
3. **Creating the repoless site config** – Creates the minimal documented repoless site config via `PUT /config/{org}/sites/{site}.json`, setting only `code.owner`, `code.repo`, and `content.source.url` with the `x-auth-token` header.
4. **Copying query index config** – Fetches the baseline `query.yaml` and creates it for the new site. Skipped if the baseline has no index config.

The new site shares the same codebase and uses `https://content.da.live/{org}/{sitename}/` as its content source.

**Edit in DA:** Open your site in Document Authoring at `https://da.live/edit#/{org}/{sitename}`

## How to Use

**Note:** Please sign in to AEM Sidekick on the Base Demo site before you initiate the Clone process.

1. Open the app from the AEM Sidekick (CloneIt button) or navigate to `/tools/cloneit/cloneit.html`
2. **Authentication** – The app must be opened from a DA context (e.g. da.live) to obtain the bearer token for API calls
3. Enter a **site name** (lowercase, numbers and hyphens only, max 50 chars, e.g. `my-new-site`). Reserved names like `admin`, `api`, `config` are blocked.
4. Click **Clone Site**
5. Access your new site at `https://main--{sitename}--{org}.aem.page`
6. **Bulk Preview/Publish** (optional) – After a successful clone, click **Bulk Preview/Publish** to copy all content URLs to your clipboard. A modal guides you to the [DA Bulk app](https://da.live/apps/bulk), where you paste the URLs and run preview or publish as needed.

---

## App Structure (for maintainers)

This section describes where things live so the app is easy to follow and change.

### File layout

All CloneIt files live under the project’s `tools/cloneit/` folder:

| File | Role |
|------|------|
| `cloneit.html` | Single-page UI: header, config card, progress section, result section, bulk modal, help modal, toast |
| `cloneit.js` | All app logic: constants, validation, API calls, clone flow, bulk flow, event wiring, init |
| `cloneit.css` | All styles (no preprocessor). Scoped by section/component class names. |
| `README.md` | This documentation |

### HTML structure (`cloneit.html`)

- **Header** – Title, subtitle, Help button
- **Config card** – Site name input, live preview URL, Clone button
- **Progress section** – Shown during clone: phase, progress bar, status text, file list
- **Result section** – Success card (summary list, Bulk Preview/Publish button, Preview/DA/Code links) or error card
- **Bulk modal** – “URLs copied” message and “Open DA Bulk app” button (no in-app bulk API)
- **Help modal** – What CloneIt does, naming rules, after-clone steps, bulk flow
- **Toast** – Temporary success/error/info messages

---

## APIs Used

| API | Endpoint | Purpose |
|-----|----------|---------|
| DA Admin | `GET /list/{org}/{baseSite}/{path}` | Discover all files recursively |
| DA Admin | `POST /copy/{org}/{baseSite}/{path}` | Copy each file to new site folder |
| DA Admin | `POST /source/{org}/{site}/index.html` | Fallback: create minimal content if copy fails |
| AEM Admin | `GET /config/{org}/sites/{baseSite}.json` | Fetch baseline config |
| AEM Admin | `PUT /config/{org}/sites/{site}.json` | Create repoless site |
| AEM Admin | `GET /config/{org}/sites/{baseSite}/content/query.yaml` | Fetch baseline index config |
| AEM Admin | `PUT /config/{org}/sites/{site}/content/query.yaml` | Create index config for new site |

## Authentication

Uses the [DA SDK](https://da.live/nx/utils/sdk.js) to obtain a bearer token. Clone-It calls DA Admin APIs with `Authorization: Bearer {token}` and AEM Admin APIs with `x-auth-token: {token}`. If the DA SDK does not provide a token on the page, the UI supports a manual bearer-token fallback stored only in the browser.

## Troubleshooting

### `Missing configuration` on `https://main--{site}--{org}.aem.page/`

This means the repoless site config was not created successfully on `admin.hlx.page`. The DA content copy may still have completed, so the clone can be partially broken.

### `invalid fstab` in DA preview

For repoless sites, this usually means the site's content-location config is missing or invalid in Config Service. It does **not** mean a literal `fstab.yaml` file must exist in the Git repo.

### Repairing or inspecting site config

Use the repo-level helper script:

```sh
python3 ../../scripts/repoless-site-config.py show --org somarc --site remixbase

python3 ../../scripts/repoless-site-config.py put \
  --org somarc \
  --site remixbase \
  --baseline-site demobase \
  --code-repo demobase \
  --copy-query-index
```

## References

- [Repoless documentation](https://www.aem.live/docs/repoless)
- [AEM Admin API – Create Site](https://www.aem.live/docs/admin.html#tag/siteConfig/operation/createSiteSite)
- [AEM Admin API – Create Index Config](https://www.aem.live/docs/admin.html#tag/indexConfig/operation/createIndexConfig)
- [DA Admin API – Create Source](https://opensource.adobe.com/da-admin/#tag/Source/operation/createSource)
- [Config Service Setup](https://www.aem.live/docs/config-service-setup)
