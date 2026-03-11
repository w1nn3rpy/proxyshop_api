IMAGE_NAME=proxy_shop_api_image
CONTAINER_NAME=proxy_shop_api
LOGS_DIR=/root/ProxyShopApi/logs
PORT=8000

build:
	 docker build -t $(IMAGE_NAME) .

run:
	@mkdir -p $(LOGS_DIR)
	docker run -d \
	 --network bot_net \
	 --name $(CONTAINER_NAME) \
	 --env-file .env \
	 -v $(LOGS_DIR):/usr/src/app/logs \
	 -p 8080:8000 \
	 --restart unless-stopped \
	 $(IMAGE_NAME)

stop:
	 docker stop $(CONTAINER_NAME)

start:
	 docker start $(CONTAINER_NAME)

rm:
	 docker rm -f $(CONTAINER_NAME)
	 docker rmi $(IMAGE_NAME)

logs:
	 docker logs -f $(CONTAINER_NAME)

update:
	 make stop
	 make rm
	 make build
	 make run

attach:
	 docker attach $(CONTAINER_NAME)

restart:
	 docker restart $(CONTAINER_NAME)
