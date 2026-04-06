import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import OpenAI from "https://esm.sh/openai@4.28.0";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL") || "",
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || ""
);

const openai = new OpenAI({
  apiKey: Deno.env.get("OPENAI_API_KEY"),
});

// --- сигналы значимости ---
function isImportant(text: string): boolean {
  const signals = ["люблю", "важно", "ненавижу", "хочу", "мне", "я"];
  return signals.some(s => text.toLowerCase().includes(s));
}

// --- получение памяти ---
async function getMemory(userId: string) {
  try {
    const { data, error } = await supabase
      .from("kuzia_interactions")
      .select("stimulus")
      .eq("user_id", userId)
      .order("timestamp", { ascending: false })
      .limit(12);

    if (error) throw error;

    return data?.map(d => d.stimulus) || [];
  } catch (e) {
    console.error("Memory error:", e);
    return [];
  }
}

// --- генерация отклика (через OpenAI) ---
async function generateResponse(input: string, userId: string) {
  const memory = await getMemory(userId);

  const context = memory.length
    ? `Вот что я помню о пользователе:\n${memory.join("\n")}`
    : "Памяти пока нет.";

  const completion = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      {
        role: "system",
        content:
          "Ты Кузя. Ты не помощник и не бот. Ты отвечаешь естественно, живо, без шаблонных советов. Ты не объясняешь очевидное. Ты держишь контекст и реагируешь по смыслу.",
      },
      {
        role: "system",
        content: context,
      },
      {
        role: "user",
        content: input,
      },
    ],
  });

  return completion.choices[0].message.content;
}

// --- сервер ---
Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, {
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST",
        "Access-Control-Allow-Headers": "Content-Type",
      },
    });
  }

  try {
    const body = await req.json();

    const message =
      body.message?.text ||
      body.message ||
      "";

    const userId =
      body.message?.from?.id?.toString() ||
      body.userId ||
      "";

    if (!message.trim() || typeof userId !== "string" || !userId.trim()) {
      return new Response(
        JSON.stringify({ error: "Invalid input" }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    const reply = await generateResponse(message, userId);

    // --- сохраняем важное ---
    if (isImportant(message)) {
      const { error } = await supabase
        .from("kuzia_interactions")
        .insert({
          user_id: userId,
          stimulus: message,
          response: reply,
          timestamp: new Date().toISOString()
        });

      if (error) {
        console.error("Insert error:", error);
      }
    }

    return new Response(
      JSON.stringify({ response: reply }), // важно: response, не reply
      { headers: { "Content-Type": "application/json" } }
    );

  } catch (e) {
    console.error("Handler error:", e);
    return new Response(
      JSON.stringify({ error: e.message }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
});
