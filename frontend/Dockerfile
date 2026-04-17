FROM node:20-alpine

WORKDIR /app

RUN npm install -g pnpm@9

COPY package.json ./
RUN pnpm install

COPY . .

EXPOSE 3000

CMD ["pnpm", "dev"]
