import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// Served from ibiraheel.com/demos/hydraulic-centerline-lens/; every asset and data fetch goes through import.meta.env.BASE_URL.
export default defineConfig({ base: '/demos/hydraulic-centerline-lens/', plugins: [react()] })
