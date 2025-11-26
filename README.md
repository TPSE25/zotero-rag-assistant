## Develop locally
Prerequisites: docker Ollama
```
cd infrastructure
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
curl http://localhost:8080/api/health 
```

## Deploy production
Prerequisites: docker
```
cd infrastructure
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
