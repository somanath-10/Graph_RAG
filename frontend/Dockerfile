FROM node:20-slim
WORKDIR /app
COPY frontend/package.json ./package.json
RUN npm install
COPY frontend ./
EXPOSE 5173
CMD ["sh", "-c", "npm run dev -- --host ${VITE_DEV_SERVER_HOST:-0.0.0.0} --port ${VITE_DEV_SERVER_PORT:-5173}"]
