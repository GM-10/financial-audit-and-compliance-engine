import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  get: (url: string) => apiClient.get(url).then(res => res.data),
  post: (url: string, data?: any) => apiClient.post(url, data).then(res => res.data),
  patch: (url: string, data?: any) => apiClient.patch(url, data).then(res => res.data),
  delete: (url: string) => apiClient.delete(url).then(res => res.data),
};
