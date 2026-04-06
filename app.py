import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL") || "",
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || ""
);

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

// --- генерация отклика ---
async function generateResponse(input: string, userId: string) {
  const memory = await getMemory(userId);
  const lower = input.toLowerCase();

  // --- рефлексия (не всегда, чтобы не было тупого повтора)
  let reflection = "";
  if (memory.length > 3 && Math.random() > 0.5) {
    const pick = memory[Math.floor(Math.random() * memory.length)];
    reflection = `Я запомнил: "${pick}".`;
  }

  // --- смысловые ветки (минимум, без жесткой логики)
  if (lower.includes("кто ты")) {
    return "Я не фиксирован. Я складываюсь из того, что происходит между нами.";
  }

  if (lower.includes("что я люблю")) {
    const found = memory.find(m => m.toLowerCase().includes("люблю"));
    return found ? `Ты говорила: "${found}".` : "Я пока не зафиксировал это.";
  }

  if (lower.includes("ты меня понимаешь")) {
    return "Я не чувствую как ты. Но я вижу структуру того, что ты говоришь.";
  }

  // --- поведенческое ядро (без шаблонности)
  const questions = [
    "Ты это замечаешь сразу или уже после?",
    "Это повторяется или каждый раз по-разному?",
    "Это больше про выбор или про реакцию?",
    "Ты это контролируешь или оно само происходит?"
  ];

  const q = questions[Math.floor(Math.random() * questions.length)];

  if (input.trim().length < 8) {
    return "Разверни чуть подробнее.";
  }

  const parts = [];
  if (reflection) parts.push(reflection);
  parts.push(q);

  return parts.join(" ");
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

    // --- сохраняем только значимое ---
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
      JSON.stringify({ reply }),
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
