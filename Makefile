flags = --no-cache --progress plain
platforms =
push = --load
version = $(shell head -1 irissqlcli/__init__.py | cut -d '"' -f2)

cli-image = caretdev/irissqlcli
web-image = caretdev/irissqlcli-web

dockerfile := Dockerfile

releases = beta latest
apps = cli web

ifeq ($(findstring b,$(version)),b)
	release = beta
else
	release = latest
endif

push: push-$(release)

build: $(release)

help:
	@echo help

cli: app = cli

web: app = web

$(apps): 
	@echo docker buildx build $(flags) $(push) $(platforms) -f $(dockerfile)-$(@) $(tags) .

beta: tags = -t $($@-image):beta

latest: tags = -t $($@-image):latest
latest: tags += -t $($@-image):$(version)

$(releases): $(apps)

$(addprefix push-, $(releases)): push = --push
$(addprefix push-, $(releases)): platforms = --platform linux/arm64,linux/amd64
push-beta: beta
push-latest: latest
