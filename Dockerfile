FROM node:22-slim
LABEL "language"="nodejs"
WORKDIR /src
COPY . .
RUN yarn install
EXPOSE 3100
CMD ["yarn", "start:sse"]
