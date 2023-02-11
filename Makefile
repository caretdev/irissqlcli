flags = --no-cache --progress plain
platforms =
push = --load

doker: cli web

push: push-cli push-web

push-cli: push = --push 
push-cli: platforms = --platform linux/arm64,linux/amd64
push-cli: cli

push-web: push = --push 
push-web: platforms = --platform linux/arm64,linux/amd64
push-web: web

cli:
	docker buildx build $(flags) $(push) $(platforms) -f Dockerfile-cli -t caretdev/irissqlcli .

web:
	docker buildx build $(flags) $(push) $(platforms) -f Dockerfile-web -t caretdev/irissqlcli-web .
