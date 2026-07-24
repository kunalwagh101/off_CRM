export type CatalogEntry = {
  id: string;
  name: string;
  flag: string;
  region: "American" | "Chinese" | "European";
  tagline: string;
  providerType: "openai" | "anthropic" | "openai_compatible";
  defaultModel: string;
  baseUrl?: string;
  keyUrl: string;
  howToGet: string;
  keyPlaceholder: string;
  defaultName: string;
};

export const PROVIDER_CATALOG: CatalogEntry[] = [
  // ── American ───────────────────────────────────────────────────────────────
  {
    id: "openai",
    name: "OpenAI",
    flag: "🇺🇸",
    region: "American",
    tagline: "GPT-4o · GPT-4.1 · o3",
    providerType: "openai",
    defaultModel: "gpt-4o",
    keyUrl: "https://platform.openai.com/api-keys",
    howToGet:
      "Sign in at platform.openai.com → API keys → Create new secret key. " +
      "Note: this is separate from your ChatGPT Plus/Pro subscription — " +
      "API usage is billed per token from a separate credit balance. " +
      "A $5 top-up easily runs thousands of emails.",
    keyPlaceholder: "sk-…",
    defaultName: "OpenAI (GPT-4o)",
  },
  {
    id: "anthropic",
    name: "Anthropic",
    flag: "🇺🇸",
    region: "American",
    tagline: "Claude Opus · Sonnet · Haiku",
    providerType: "anthropic",
    defaultModel: "claude-sonnet-4-5",
    keyUrl: "https://console.anthropic.com/settings/keys",
    howToGet:
      "Go to console.anthropic.com → Settings → API keys → Create key. " +
      "Separate from your Claude.ai Pro account — the API has its own pay-per-token billing. " +
      "claude-sonnet-4-5 is the best balance of quality and cost for email generation.",
    keyPlaceholder: "sk-ant-…",
    defaultName: "Anthropic (Claude Sonnet)",
  },
  {
    id: "xai",
    name: "xAI (Grok)",
    flag: "🇺🇸",
    region: "American",
    tagline: "Grok-3 · Grok-3 mini",
    providerType: "openai_compatible",
    defaultModel: "grok-3",
    baseUrl: "https://api.x.ai/v1",
    keyUrl: "https://console.x.ai",
    howToGet:
      "Sign up at console.x.ai → API → Create API key. " +
      "Grok-3 uses the same API format as OpenAI so off_CRM connects to it instantly. " +
      "Free tier available with generous monthly credits.",
    keyPlaceholder: "xai-…",
    defaultName: "xAI (Grok-3)",
  },
  {
    id: "google",
    name: "Google Gemini",
    flag: "🇺🇸",
    region: "American",
    tagline: "Gemini 2.0 Flash · 1.5 Pro",
    providerType: "openai_compatible",
    defaultModel: "gemini-2.0-flash",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    keyUrl: "https://aistudio.google.com/app/apikey",
    howToGet:
      "Go to aistudio.google.com → Get API key → Create API key. " +
      "Gemini 2.0 Flash is fast and cheap. Google provides a generous free tier. " +
      "Gemini exposes an OpenAI-compatible endpoint so it plugs straight in.",
    keyPlaceholder: "AIza…",
    defaultName: "Google (Gemini 2.0 Flash)",
  },
  {
    id: "nvidia",
    name: "NVIDIA NIM",
    flag: "🇺🇸",
    region: "American",
    tagline: "LLaMA 3.1 · Mistral · Nemotron",
    providerType: "openai_compatible",
    defaultModel: "meta/llama-3.1-70b-instruct",
    baseUrl: "https://integrate.api.nvidia.com/v1",
    keyUrl: "https://build.nvidia.com",
    howToGet:
      "Go to build.nvidia.com → sign in → Get API key. " +
      "NVIDIA NIM runs many open-source models (LLaMA, Mistral, Nemotron) " +
      "on NVIDIA's infrastructure. Useful if you want open-weight quality without local GPU.",
    keyPlaceholder: "nvapi-…",
    defaultName: "NVIDIA NIM",
  },
  {
    id: "groq",
    name: "Groq",
    flag: "🇺🇸",
    region: "American",
    tagline: "LLaMA 3.3 70B · Mixtral — ultra fast",
    providerType: "openai_compatible",
    defaultModel: "llama-3.3-70b-versatile",
    baseUrl: "https://api.groq.com/openai/v1",
    keyUrl: "https://console.groq.com/keys",
    howToGet:
      "Sign up at console.groq.com → API Keys → Create. " +
      "Groq runs open-source models on custom hardware — it's the fastest inference available. " +
      "Free tier is very generous. Great choice if speed matters more than GPT-4-level quality.",
    keyPlaceholder: "gsk_…",
    defaultName: "Groq (LLaMA 3.3 70B)",
  },
  {
    id: "perplexity",
    name: "Perplexity",
    flag: "🇺🇸",
    region: "American",
    tagline: "Sonar Pro · Sonar — online LLMs",
    providerType: "openai_compatible",
    defaultModel: "sonar-pro",
    baseUrl: "https://api.perplexity.ai",
    keyUrl: "https://www.perplexity.ai/settings/api",
    howToGet:
      "Go to perplexity.ai → Settings → API → Generate. " +
      "Sonar models have live web access built in, so research prompts can pull fresh company data. " +
      "Useful if you want web-grounded lead context in the email draft.",
    keyPlaceholder: "pplx-…",
    defaultName: "Perplexity (Sonar Pro)",
  },

  // ── Chinese ────────────────────────────────────────────────────────────────
  {
    id: "deepseek",
    name: "DeepSeek",
    flag: "🇨🇳",
    region: "Chinese",
    tagline: "DeepSeek-V3 · R1 (reasoning)",
    providerType: "openai_compatible",
    defaultModel: "deepseek-chat",
    baseUrl: "https://api.deepseek.com/v1",
    keyUrl: "https://platform.deepseek.com/api_keys",
    howToGet:
      "Sign up at platform.deepseek.com → API keys → Create. " +
      "DeepSeek-V3 matches GPT-4o quality at a fraction of the cost — " +
      "roughly 30× cheaper per token. One of the best value-for-money picks for bulk email generation. " +
      "Uses the same API format as OpenAI.",
    keyPlaceholder: "sk-…",
    defaultName: "DeepSeek (V3)",
  },
  {
    id: "qwen",
    name: "Qwen (Alibaba)",
    flag: "🇨🇳",
    region: "Chinese",
    tagline: "Qwen-Max · Qwen-Plus · Qwen-Turbo",
    providerType: "openai_compatible",
    defaultModel: "qwen-max",
    baseUrl: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    keyUrl: "https://dashscope.aliyuncs.com",
    howToGet:
      "Sign up at alibaba.cloud or dashscope.aliyuncs.com → Console → Model Studio → API keys. " +
      "Qwen-Max is Alibaba's frontier model, strong at multilingual and structured output. " +
      "The international endpoint above avoids needing a mainland China account.",
    keyPlaceholder: "sk-…",
    defaultName: "Qwen Max",
  },
  {
    id: "moonshot",
    name: "Moonshot AI (Kimi)",
    flag: "🇨🇳",
    region: "Chinese",
    tagline: "Moonshot-v1 — long context",
    providerType: "openai_compatible",
    defaultModel: "moonshot-v1-128k",
    baseUrl: "https://api.moonshot.cn/v1",
    keyUrl: "https://platform.moonshot.cn/console/api-keys",
    howToGet:
      "Sign up at platform.moonshot.cn → API keys → New key. " +
      "Kimi supports 128K context — useful if you want to feed an entire company report into the prompt. " +
      "OpenAI-compatible format.",
    keyPlaceholder: "sk-…",
    defaultName: "Moonshot (Kimi 128K)",
  },
  {
    id: "zhipu",
    name: "Zhipu AI (GLM)",
    flag: "🇨🇳",
    region: "Chinese",
    tagline: "GLM-4-Plus · GLM-4-Flash",
    providerType: "openai_compatible",
    defaultModel: "glm-4-plus",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    keyUrl: "https://open.bigmodel.cn/usercenter/apikeys",
    howToGet:
      "Register at open.bigmodel.cn → User Center → API keys → Create. " +
      "GLM-4-Plus is strong at Chinese-language content and logical reasoning. " +
      "GLM-4-Flash is extremely cheap for high-volume use.",
    keyPlaceholder: "…",
    defaultName: "Zhipu (GLM-4-Plus)",
  },

  // ── European ───────────────────────────────────────────────────────────────
  {
    id: "mistral",
    name: "Mistral AI",
    flag: "🇫🇷",
    region: "European",
    tagline: "Mistral Large · Small · Codestral",
    providerType: "openai_compatible",
    defaultModel: "mistral-large-latest",
    baseUrl: "https://api.mistral.ai/v1",
    keyUrl: "https://console.mistral.ai/api-keys",
    howToGet:
      "Sign up at console.mistral.ai → API keys → Create. " +
      "Mistral Large is a strong European-built frontier model. " +
      "GDPR-friendly option for EU data residency requirements. " +
      "OpenAI-compatible format, connects instantly.",
    keyPlaceholder: "…",
    defaultName: "Mistral (Large)",
  },
  {
    id: "cohere",
    name: "Cohere",
    flag: "🇨🇦",
    region: "European",
    tagline: "Command R+ · Command R — enterprise RAG",
    providerType: "openai_compatible",
    defaultModel: "command-r-plus",
    baseUrl: "https://api.cohere.com/compatibility/v1",
    keyUrl: "https://dashboard.cohere.com/api-keys",
    howToGet:
      "Sign up at dashboard.cohere.com → API keys → New trial key (free). " +
      "Command R+ is purpose-built for retrieval-augmented generation — " +
      "excellent when your emails pull heavily from the local knowledge base. " +
      "Now exposes an OpenAI-compatible endpoint.",
    keyPlaceholder: "…",
    defaultName: "Cohere (Command R+)",
  },
  {
    id: "together",
    name: "Together AI",
    flag: "🇺🇸",
    region: "American",
    tagline: "LLaMA · Qwen · Mistral — all on one API",
    providerType: "openai_compatible",
    defaultModel: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    baseUrl: "https://api.together.xyz/v1",
    keyUrl: "https://api.together.xyz/settings/api-keys",
    howToGet:
      "Sign up at together.ai → Settings → API keys → Create. " +
      "Together gives you access to 50+ open-source models (LLaMA, Qwen, Mistral, DBRX) " +
      "from one API key — great if you want to compare models without signing up to each separately.",
    keyPlaceholder: "…",
    defaultName: "Together AI (LLaMA 3.3 70B)",
  },
];

export const REGIONS = ["American", "Chinese", "European"] as const;
export type Region = (typeof REGIONS)[number];

export const REGION_FLAGS: Record<Region, string> = {
  American: "🇺🇸",
  Chinese: "🇨🇳",
  European: "🇪🇺",
};
