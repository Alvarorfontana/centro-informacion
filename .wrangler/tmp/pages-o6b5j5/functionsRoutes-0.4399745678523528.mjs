import { onRequest as __api_publicar_js_onRequest } from "/home/claude/centro-informacion/functions/api/publicar.js"
import { onRequest as __api_reformular_js_onRequest } from "/home/claude/centro-informacion/functions/api/reformular.js"

export const routes = [
    {
      routePath: "/api/publicar",
      mountPath: "/api",
      method: "",
      middlewares: [],
      modules: [__api_publicar_js_onRequest],
    },
  {
      routePath: "/api/reformular",
      mountPath: "/api",
      method: "",
      middlewares: [],
      modules: [__api_reformular_js_onRequest],
    },
  ]