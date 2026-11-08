export type WritingStyle = "professional" | "articulate" | "concise" | "confident" | "recruiter-friendly" | "academic";
export interface EnhanceResponse { original_text: string; enhanced_text: string; style: WritingStyle }

type AnnaRuntime = {
  tools: {
    invoke: (
      request: { tool_id: string; method: string; args: Record<string, unknown> },
      options?: { timeoutMs?: number },
    ) => Promise<unknown>;
  };
};

declare global {
  interface Window { __ANNA_TOOL_IDS__?: Record<string, string> }
}

const HANDLE = "lexyra-writer";
const LOCAL_TOOL_ID = "tool-dev-lexyra-writer";
let runtimePromise: Promise<AnnaRuntime> | undefined;

async function connectRuntime(): Promise<AnnaRuntime> {
  if (!runtimePromise) {
    // @ts-expect-error The Anna host provides this module; it is not an npm dependency.
    runtimePromise = import("/static/anna-apps/_sdk/latest/index.js")
      .then(async ({ AnnaAppRuntime }) => AnnaAppRuntime.connect() as Promise<AnnaRuntime>)
      .catch((error: unknown) => {
        runtimePromise = undefined;
        throw error;
      });
  }
  return runtimePromise;
}

export async function checkHealth(): Promise<boolean> {
  try { await connectRuntime(); return true; } catch { return false; }
}

export async function enhanceText(text: string, style: WritingStyle): Promise<EnhanceResponse> {
  if (!text.trim()) throw new Error("Add some text before enhancing it.");
  const anna = await connectRuntime();
  const toolId = window.__ANNA_TOOL_IDS__?.[HANDLE] || LOCAL_TOOL_ID;
  let response: unknown;
  try {
    response = await anna.tools.invoke(
      { tool_id: toolId, method: "enhance", args: { text, style } },
      { timeoutMs: 120_000 },
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "The Anna writing service could not complete the request.";
    if (/SAMPLING_NOT_GRANTED|NOT_GRANTED|sampling.*grant/i.test(message)) {
      throw new Error("Anna needs permission to use its language model for this Executa. Grant Sampling access, then try again.");
    }
    if (/timeout|timed out/i.test(message)) throw new Error("The enhancement took too long. Please try again.");
    throw new Error(message || "Lexyra couldn't enhance your writing. Please try again.");
  }

  const outer = asRecord(response);
  if (!outer) throw new Error("Anna returned an unexpected response. Please try again.");
  if (outer.success === false) throw new Error(asString(outer.error) || "Lexyra couldn't enhance your writing. Please try again.");
  const payload = asRecord(outer.data) ?? outer;
  const enhanced = asString(payload.enhanced_text);
  if (!enhanced?.trim()) throw new Error("Anna returned an empty result. Please try again.");
  if (payload.style !== style) throw new Error("Anna returned a result for a different writing style. Please try again.");
  return { original_text: text, enhanced_text: enhanced.trim(), style };
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : undefined;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}
