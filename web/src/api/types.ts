/**
 * Wire types mirroring api/serialize.py. Keep the two in step: the Python side
 * emits camelCase specifically so these map one-to-one.
 */

export interface DemoSettings {
  awsRegion: string;
  awsProfile: string | null;
  modelId: string;
  gatewayUrl: string;
  gatewayRegion: string;
  gatewayConfigured: boolean;
  maxResults: number;
  domainInclude: string[];
  domainExclude: string[];
  publishedFrom: string | null;
  publishedTo: string | null;
  filtersActive: boolean;
  filtersSummary: string;
  searchFilters: SearchFilters;
}

export interface SearchFilters {
  domainFilter?: { include?: string[]; exclude?: string[] };
  publishedDateFilter?: { from?: string; to?: string };
}

/** Settings the browser sends up. Credentials stay server-side. */
export interface SettingsPayload {
  modelId: string;
  gatewayUrl: string;
  maxResults: number;
  domainInclude: string[];
  domainExclude: string[];
  publishedFrom: string | null;
  publishedTo: string | null;
}

export interface Constraints {
  maxQueryChars: number;
  maxResultsRange: [number, number];
  maxDomainsPerList: number;
  webSearchRegions: string[];
  searchUsdPerQuery: number;
}

export interface ModelOption {
  id: string;
  label: string;
}

export interface Bootstrap {
  settings: DemoSettings;
  modelOptions: ModelOption[];
  sampleQuestions: string[];
  constraints: Constraints;
}

export interface ModeInfo {
  key: string;
  number: number;
  label: string;
  title: string;
  tagline: string;
  icon: string;
  explanation: string[];
  ready: boolean;
  readyReason: string;
  /** Whether the search tool is offered to the model at all. */
  offersSearch: boolean;
}

export interface Readiness {
  credentials: { ok: boolean; message: string };
  gateway: {
    configured: boolean;
    region: string;
    regionSupported: boolean | null;
  };
  modes: ModeInfo[];
  settings: DemoSettings;
}

export interface Citation {
  title: string;
  displayTitle: string;
  url: string;
  domain: string;
  publishedDate: string;
  snippet: string;
}

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
  resultSummary: string;
  /** Complete payload, exactly as returned and exactly as sent to the model. */
  rawResult: string;
  rawResultChars: number;
  durationSeconds: number;
  error: string | null;
}

export interface RunMetrics {
  latencySeconds: number;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  modelCycles: number;
  searchQueries: number;
  modelCostUsd: number;
  searchCostUsd: number;
  totalCostUsd: number;
}

export interface RunResult {
  modeKey: string;
  question: string;
  answer: string;
  ok: boolean;
  grounded: boolean;
  error: string | null;
  trace: string[];
  citations: Citation[];
  toolCalls: ToolCall[];
  metrics: RunMetrics;
}

export interface RunResponse {
  result: RunResult;
  filtersApplied: SearchFilters;
}

export interface ArchitectureOption {
  key: string;
  number: number;
  title: string;
  tagline: string;
  summary: string;
  diagramSvg: string;
  components: {
    component: string;
    operatedBy: string;
    responsibility: string;
  }[];
  requestFlow: string[];
  youOwn: string[];
  awsOwns: string[];
  security: { name: string; value: string }[];
  cost: { name: string; value: string }[];
  codeCaption: string;
  code: string;
  iam: string | null;
  links: { label: string; url: string }[];
}

export interface ComparisonRow {
  dimension: string;
  noSearch: string;
  withAgentCore: string;
}

export interface Comparison {
  rows: ComparisonRow[];
  closingPoints: string[];
}
