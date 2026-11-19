"use client";

import { useState, useRef, useEffect } from "react";
import { Bot, Loader2, Send, Sparkles, User } from "lucide-react";
import { sendChatMessage } from "@/lib/api";
import type { ChatMessage, StudentRecord } from "@/lib/types";

interface AdvisorChatProps {
  student: StudentRecord;
}

const QUICK_PROMPTS = [
  {
    label: "اقترح لي مواد الفصل القادم",
    prompt:
      "ما هي المقررات التي تنصحني بتسجيلها في الفصل القادم بناءً على المتطلبات السابقة وموقفي الأكاديمي في اللائحة؟",
  },
  {
    label: "ما موقفي من مرتبة الشرف؟",
    prompt: "هل أنا مؤهل للحصول على مرتبة الشرف عند التخرج وفقاً للائحة الكلية وسجلي الحالي؟",
  },
  {
    label: "ما هي شروط الإنذار والعبء الدراسي؟",
    prompt: "ما هي قواعد الإنذار الأكاديمي والحد الأقصى للساعات المسموح بها في لائحة الكلية؟",
  },
  {
    label: "كم ساعاتي بعد نهاية هذا الفصل؟",
    prompt: "بعد اجتياز مقرراتي المسجلة حالياً، كم ستصبح ساعاتي المنجزة وكم ساعة متبقية للتخرج؟",
  },
];

export default function AdvisorChat({ student }: AdvisorChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "مرحباً بك! أنا مرشدك الأكاديمي الذكي. أعتمد على لائحة الكلية الرسمية وأدوات الحساب الدقيقة لمساعدتك في اختيار موادك، محاكاة معدلك التراكمي (GPA)، والتحقق من شروط التخرج والإنذارات.\n\nكيف يمكنني مساعدتك اليوم؟",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (textOverride?: string) => {
    const query = (textOverride ?? input).trim();
    if (!query || loading) return;

    const historySnapshot = messages.slice(-10);
    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: query }];
    setMessages(nextMessages);
    setInput("");
    setError(null);
    setLoading(true);

    try {
      const res = await sendChatMessage({
        message: query,
        student_record: student,
        history: historySnapshot,
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.response,
          modelUsed: res.model_used,
        },
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "حدث خطأ غير متوقع أثناء الاتصال بالمرشد.";
      setError(msg);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `تعذر الحصول على رد من السيرفر حالياً: ${msg}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Quick prompts */}
      <div className="flex flex-wrap gap-2">
        {QUICK_PROMPTS.map((q) => (
          <button
            key={q.label}
            type="button"
            disabled={loading}
            onClick={() => handleSend(q.prompt)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700/80 bg-slate-900/90 px-3.5 py-2 text-xs font-medium text-slate-200 transition hover:border-sky-500/60 hover:bg-slate-800 hover:text-sky-300 disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5 text-sky-400" />
            {q.label}
          </button>
        ))}
      </div>

      {/* Chat Messages Area */}
      <div className="flex h-[500px] flex-col rounded-2xl border border-slate-800 bg-slate-950/70 shadow-inner">
        <div className="flex-1 space-y-4 overflow-y-auto p-4 md:p-5">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex items-start gap-3 ${
                msg.role === "user" ? "flex-row-reverse" : "flex-row"
              }`}
            >
              <div
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                  msg.role === "user"
                    ? "bg-sky-600 text-white"
                    : "bg-slate-800 text-sky-400 border border-slate-700"
                }`}
              >
                {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-7 whitespace-pre-wrap ${
                  msg.role === "user"
                    ? "bg-sky-600/20 border border-sky-500/30 text-slate-100"
                    : "bg-slate-900 border border-slate-800 text-slate-200"
                }`}
              >
                {msg.content}
                {msg.modelUsed && (
                  <div className="mt-2 border-t border-slate-800 pt-1.5 text-[11px] text-slate-500">
                    Model: {msg.modelUsed}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-700 bg-slate-800 text-sky-400">
                <Bot className="h-4 w-4" />
              </div>
              <div className="inline-flex items-center gap-2 rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-300">
                <Loader2 className="h-4 w-4 animate-spin text-sky-400" />
                <span>جاري مراجعة اللائحة وحساب الأدوات...</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="border-t border-slate-800 bg-slate-900/80 p-3"
        >
          {error && (
            <div className="mb-2 rounded-lg bg-rose-500/10 px-3 py-1.5 text-xs text-rose-300">
              {error}
            </div>
          )}
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="اكتب سؤالك للمرشد الأكاديمي (مثلاً: ما المواد المفتوحة لي السمستر الجاي؟)..."
              disabled={loading}
              className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white placeholder:text-slate-500 focus:border-sky-500 focus:outline-none disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="inline-flex items-center gap-1.5 rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              إرسال
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
