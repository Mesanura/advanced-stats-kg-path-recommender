import axios from 'axios'

export const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  timeout: 10000,
})

