import axios from "axios";

export const API_BASE_URL = import.meta.env.PROD ? "" : "http://localhost:8080";

const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

export default http;
