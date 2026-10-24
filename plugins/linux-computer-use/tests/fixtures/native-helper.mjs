import { createInterface } from 'node:readline';
createInterface({ input: process.stdin }).on('line', async line => {
  const request = JSON.parse(line);
  if (request.method === 'slow') await new Promise(resolve => setTimeout(resolve, 30000));
  if (request.method === 'crash') process.exit(3);
  process.stdout.write(JSON.stringify({ id: request.id, result: { method: request.method, pid: process.pid } }) + '\n');
});
