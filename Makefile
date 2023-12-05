.PHONY: help docker .git-blame-ignore-revs
.DEFAULT: help

tag="latest"

help:
	@echo "Premade recipes"
	@echo
	@echo "make docker [tag=TAG]"
	@echo "\tBuilds a docker image from source. Defaults to 'latest' tag."


docker:
	docker build --rm -t nipreps/smriprep:$(tag) \
	--build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"` \
	--build-arg VCS_REF=`git rev-parse --short HEAD` \
	--build-arg VERSION=`python setup.py --version` .


.git-blame-ignore-revs:
	git log --grep "\[git-blame-ignore-rev\]" --pretty=format:"# %ad - %ae - %s%n%H" --date short \
		> .git-blame-ignore-revs
	echo >> .git-blame-ignore-revs
