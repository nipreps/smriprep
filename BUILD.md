
## Generate base image
```
docker build -t ghcr.io/vferat/smriprep-base:20251104 -f  ./Dockerfile.base .
```

## build smriprep

```
docker build -t ghcr.io/vferat/smriprep:0.19.1 .
```