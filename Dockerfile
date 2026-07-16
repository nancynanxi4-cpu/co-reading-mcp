FROM node:22-slim
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY . .
RUN yarn install
EXPOSE 3100
CMD ["yarn", "start:sse"]
