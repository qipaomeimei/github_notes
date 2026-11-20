'use strict';

const http = require('node:http');
const config = require('./config');
const { createApp } = require('./app');

async function main() {
  const app = await createApp({ dbPath: config.DB_FILE });
  const server = http.createServer((req, res) => app.handle(req, res));

  server.listen(config.PORT, config.HOST, () => {
    console.log(`CampusEvent 已启动：http://${config.HOST}:${config.PORT}`);
    console.log(`数据库文件：${config.DB_FILE}`);
  });

  const shutdown = () => {
    server.close(() => {
      app.close();
      process.exit(0);
    });
  };
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

main().catch((err) => {
  console.error('启动失败：', err);
  process.exit(1);
});
