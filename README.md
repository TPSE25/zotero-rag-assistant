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
