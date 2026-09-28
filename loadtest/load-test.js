import http from 'k6/http';
import { sleep, check } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 50 },
    { duration: '1m', target: 100 },
    { duration: '30s', target: 0 },
  ],
};

const BASE_URL = 'https://se-cb38813f3aca4a9b8c391d482fea4411.ecs.eu-west-3.on.aws';

export default function () {
  const res = http.get(`${BASE_URL}/services`);
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(1);
}

