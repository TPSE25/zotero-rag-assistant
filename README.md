## Install plugin
### Create build file
```bash
cd zotero-plugin
npm ci
npm run build
```
You can then find the build file in zotero-plugin/.scaffold/build/rag-assistant.xpi 
### VPN
In order to be able to use the plugin, you must be approved by the administrators to use the VPN. Consult the [installation guide](Installationsguide___Zotero_Plugin.pdf) for more information.
### Install the plugin in Zotero
- Navigate to tools/plugins in the menu bar of Zotero
- Click the gear icon, then click the option "install plugin from file..." and select the build file
- Open the Zotero Settings and go to Sync
- Make sure you are logged in and then change "Sync attachment files in My Library using" to **WebDav**
- Set the URL to http://192.168.2.252:8080/webdav and enter any username and password
- Go to RAG Assistant and enter http://192.168.2.252:8080/ for the API base URL
- Scroll to the bottom and click reload prompts

## Setup and run
> **Note**: You need to have Docker **and the compose plugin** installed and running on your system.  
> You can find the official installation guides here:
> - **macOS**: [OrbStack](https://orbstack.dev/download) or [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/)
> - **Windows**: [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
> - **Linux**: [Docker Engine](https://docs.docker.com/engine/install/)

### Develop locally
[Install Ollama](https://ollama.com/) and make sure it's running on port 11434.
```bash
cd infrastructure
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

### Reindex all WebDAV files
```bash
cd infrastructure
docker compose exec webdav python /app/reindex_all.py
```

### Production Deployment
```bash
# Optional: Create document Volume if you dont want a host volume (ie. on a cloud provider or via nfs)
docker volume create \
  --driver xy \
  --opt xy=xy \
  documents
cd infrastructure
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
