import HomeView from '@/views/HomeView.vue'
import ScheduleView from '@/views/ScheduleView.vue'
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      name: "home",
      component: HomeView
    },
    // {
    //   path: "/tool",
    //   name: "toolbar",
    //   component: ScheduleToolbar
    // },
    {
      path: "/schedule",
      name: "schedule",
      component: ScheduleView
    }
  ],
})

export default router
