

first, build the base image
```
docker build -t ghcr.io/vferat/smriprep-base:20251104 -f .\Dockerfile.base .
```

The, build the full image
```
docker build -t  ghcr.io/vferat/smriprep:0.19.1-dev  . 
 ```