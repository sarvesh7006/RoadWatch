import { defineConfig } from 'vite';
export default defineConfig({server:{proxy:{'/api':'http://127.0.0.1:8011','/media':'http://127.0.0.1:8011'}},build:{outDir:'dist'}});
