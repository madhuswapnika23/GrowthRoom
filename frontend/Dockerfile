FROM node:20-alpine

WORKDIR /app

# Install deps first (layer cache)
COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

# Vite needs --host to be reachable inside Docker
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
