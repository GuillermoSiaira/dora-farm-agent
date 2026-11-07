# Dónde pedir financiamiento y cómputo (relevamiento del 7/11/2026)

Cruce del relevamiento de la IA de Google con lo que ya teníamos, verificado en las páginas oficiales cuando se pudo. Situación de partida: investigador independiente (M2M Labs), sin sociedad, autofinanciado, con DORA funcionando en público y los experimentos E1 a E10 medidos.

**Regla para no desgastarnos:** si un programa pide sociedad constituida, inversores o pertenecer a una institución y no hay manera honesta de cumplirlo, no se pide. Cada pedido se prepara una sola vez, con los textos reutilizables de la agenda.

## 1. Ya disponible, sin pedir nada

| Fuente | Qué hay | Estado | Para qué |
|---|---|---|---|
| Kaggle Benchmarks (proxy de modelos) | 10 USD por día y 100 USD por mes, gratis | verificado con `kaggle benchmarks quota` | Claude, GPT, Gemini, Gemma 4, gpt-oss-120b y Grok sobre DORA como benchmark de Kaggle |
| Kaggle Notebooks | GPU gratis con cupo semanal | script listo en `infra/kaggle/` | modelos abiertos chicos y medianos con vLLM |
| Modal (plan Starter) | 30 USD por mes | en uso (14,77 en noviembre) | app y MCP públicos; algún tamaño abierto |
| AWS | 52,60 USD de crédito | Bedrock bloqueado hasta que AWS suba la cuota (caso 179405679100577) | GLM, Kimi, DeepSeek v3.2, Qwen3, Gemma 3, Ministral |
| Alibaba Cloud, cuenta nueva | según la IA de Google: 200 USD de crédito inicial y tokens gratis de Model Studio (Qwen, DeepSeek, GLM, Kimi) | **a verificar**: abrir una cuenta personal y ver qué da | familia Qwen por API |

## 2. Pedidos que encajan y aceptan a un investigador independiente

Ordenados por fecha de cierre y probabilidad.

| # | Programa | Qué da | Requisitos verificados | Cierre | Encaje |
|---|---|---|---|---|---|
| 1 | **Mozilla Foundation, Human-Scale AI** | 300.000 USD por 12 meses desde abril de 2027, más hasta 200.000 de seguimiento | No hace falta ser ONG: hay que poder recibir fondos y que el proyecto tenga fin de bien público. Busca tecnología **ya desplegada con la gente para la que se diseñó**, que cumpla los tres principios: chica (modelos chicos, menos cómputo), intencional (control del usuario sobre sus datos) y a medida (un problema y una comunidad concretos). Primera etapa: propuesta inicial; solo unos pocos pasan a la solicitud completa. **Advierte que revisa con más cuidado las solicitudes que parezcan escritas por IA.** | **20/11/2026, 23:59 PST.** Charla informativa: 12/11, 17:00 UTC | Alto en lo técnico: DORA hace que un modelo chico y barato dé respuestas exactas (E9, E10). Lo flojo es la parte de comunidad: hay que mostrar productores que lo usen o lo hayan probado |
| 2 | **Kaggle, Benchmarks Resource Grant** | cuota de cómputo, soporte, contacto con el equipo de Kaggle | Benchmark nuevo hecho con el SDK `kaggle-benchmarks`, publicación abierta. Pide pertenecer a una institución, laboratorio u ONG: se presenta como M2M Labs, laboratorio independiente, diciéndolo claro | La ronda de 2026 cerró el 28/10; lo que entre ahora va a la siguiente | Muy alto: es justo lo que vamos a construir. Conviene pedirlo con el benchmark ya publicado |
| 3 | **OpenAI, Researcher Access Program** | hasta 1.000 USD en créditos de API, por 12 meses | Formulario oficial en openai.com; según fuentes secundarias acepta investigadores individuales, con foco en impacto social y uso responsable | abierto, sin fecha | Medio: el ángulo es la verificación (respuestas exactas y auditables) |
| 4 | **Anthropic, AI for Science** | créditos de API (monto no publicado en la página oficial) | Las reglas aceptan personas mayores de 18; el anuncio habla de investigadores de instituciones y de biología, aunque nombra la productividad agrícola entre los objetivos | abierto, sin fecha | Medio: agro y verificación de números; hay que justificar el impacto científico |
| 5 | **Google, TPU Research Cloud** | TPU gratis | Para investigadores, con compromiso de publicar | abierto | Alto para la etapa de entrenamiento (verificador como recompensa), no para ahora |
| 6 | **Hugging Face, community grants** | GPU temporal para un Space | Se pide en la discusión del Space; priorizan demos que use mucha gente | abierto | Bajo-medio: una demo de DORA con modelo chico |

## 3. No aplican hoy (piden sociedad, inversores o startup)

| Programa | Motivo |
|---|---|
| NVIDIA Inception (con los 7.500 USD de Lambda) | Pide empresa constituida, sitio web y al menos un desarrollador empleado; la IA de Google decía que no, pero las fuentes coinciden en que sí hace falta sociedad |
| Anthropic Startup Program, OpenAI for Startups | Para startups, en general a través de fondos de inversión |
| Together AI, Baseten, Modal (créditos de startup), Alibaba AI Catalyst, Cloudflare y DigitalOcean para startups | Piden ronda de inversión o empresa |
| Ramp, Brex, Mercury, JoinSecret | Piden empresa con cuenta operativa o una membresía paga |
| RunPod (1.000 USD), Salad, Runware | Montos de la IA de Google sin verificar; revisar solo si hace falta GPU dedicada |

## Plan

1. **Ahora:** DORA como benchmark de Kaggle, con los 100 USD por mes del proxy. Da resultados con modelos de punta y es el requisito del grant de Kaggle.
2. **Hasta el 20/11:** propuesta inicial para Mozilla. Guillermo la escribe con su voz (Mozilla revisa con más cuidado las solicitudes que parecen escritas por IA); yo preparo los datos, la estructura y la revisión. Conviene ir a la charla del 12/11.
3. **Esta semana, en paralelo:** OpenAI Researcher Access y Anthropic AI for Science (formularios cortos), y abrir la cuenta personal de Alibaba para ver qué crédito da.
4. **Con el benchmark publicado:** Kaggle Benchmarks Resource Grant.
5. **Cuando empiece el entrenamiento:** Google TPU Research Cloud.

Fuentes consultadas: [Kaggle Research Grants](https://www.kaggle.com/research-grants), [Mozilla Human-Scale AI](https://www.mozillafoundation.org/en/what-we-do/grantmaking/incubator/human-scale-ai/call-for-proposals/), [Anthropic AI for Science](https://www.anthropic.com/news/ai-for-science-program) y [sus reglas](https://www.anthropic.com/ai-for-science-program-rules), [OpenAI Researcher Access](https://openai.com/form/researcher-access-program) y [su FAQ](https://help.openai.com/en/articles/10139500-researcher-access-program-faq), [TPU Research Cloud](https://sites.research.google/trc/about/), guías de terceros sobre [NVIDIA Inception](https://hub.causo.ai/guides/how-to-apply-to-nvidia-inception-2026) y [Hugging Face Spaces GPU](https://huggingface.co/docs/hub/spaces-gpus).
