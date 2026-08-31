import React, { useState, useEffect } from "react";
import { History, Award, Calendar, RotateCcw } from "lucide-react";
import api from "../api/client";

const QuizHistory = ({ onStartNewQuiz }) => {
  const [attempts, setAttempts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchHistory = async () => {
    try {
      setIsLoading(true);
     const res = await api.get("/quiz/history/attempts");

console.log("COMPLETED AT:", res.data[0]?.completed_at);

setAttempts(res.data);
    } catch (err) {
      console.error("Failed to load quiz history", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const getBadgeColor = (diff) => {
    switch (diff) {
      case "Easy":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
      case "Hard":
        return "text-rose-400 bg-rose-500/10 border-rose-500/30";
      default:
        return "text-indigo-400 bg-indigo-500/10 border-indigo-500/30";
    }
  };
const formatDateTime = (dateString) => {
  // Backend stores UTC but SQLite may return it without timezone information
  const utcDate = new Date(
    dateString.endsWith("Z") || dateString.includes("+")
      ? dateString
      : `${dateString}Z`,
  );

  return {
    date: utcDate.toLocaleDateString("en-IN", {
      timeZone: "Asia/Kolkata",
    }),
    time: utcDate.toLocaleTimeString("en-IN", {
      timeZone: "Asia/Kolkata",
      hour: "2-digit",
      minute: "2-digit",
    }),
  };
};
  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20 shadow-lg">
            <History className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white tracking-tight">
              Quiz Attempt History
            </h2>
            <p className="text-xs text-slate-400">
              Track your progress and revision scores across all study topics.
            </p>
          </div>
        </div>

        <button
          onClick={onStartNewQuiz}
          className="py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl flex items-center gap-2 shadow-lg shadow-indigo-500/20 transition-all"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          New Quiz
        </button>
      </div>

      {/* Table / List */}
      {isLoading ? (
        <div className="text-center py-12 text-slate-500">
          Loading attempt history...
        </div>
      ) : attempts.length === 0 ? (
        <div className="text-center py-16 bg-slate-900/40 rounded-3xl border border-slate-800 p-8">
          <Award className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h4 className="text-base font-bold text-slate-300">
            No Quizzes Taken Yet
          </h4>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Generate an AI quiz from your uploaded study notes to test your
            understanding!
          </p>
          <button
            onClick={onStartNewQuiz}
            className="mt-5 py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-500/20 transition-all"
          >
            Create Your First Quiz
          </button>
        </div>
      ) : (
        <div className="bg-slate-900/80 border border-slate-800 rounded-3xl overflow-hidden backdrop-blur-sm">
          <div className="divide-y divide-slate-800/80">
            {attempts.map((att) => {
              const isHigh = att.percentage >= 80;
              const isPass = att.percentage >= 60;
             
 

  const { date, time } = formatDateTime(att.completed_at);

              return (
                <div
                  key={att.id}
                  className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-800/40 transition-colors"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${getBadgeColor(att.difficulty)}`}
                      >
                        {att.difficulty}
                      </span>
                      <h4 className="text-sm font-bold text-white">
                        {att.quiz_title}
                      </h4>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-slate-400">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-slate-500" />
                     {date} at {time}
                      </span>
                      <span>•</span>
                      <span>{att.total_questions} Questions</span>
                    </div>
                  </div>

                  {/* Score pill */}
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-lg font-black text-white">
                        {att.score} / {att.total_questions}
                      </div>
                      <div
                        className={`text-xs font-bold ${
                          isHigh
                            ? "text-emerald-400"
                            : isPass
                              ? "text-indigo-400"
                              : "text-amber-400"
                        }`}
                      >
                        {att.percentage}% Score
                      </div>
                    </div>

                    <div
                      className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-xs ${
                        isHigh
                          ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                          : isPass
                            ? "bg-indigo-500/10 text-indigo-300 border border-indigo-500/20"
                            : "bg-amber-500/10 text-amber-300 border border-amber-500/20"
                      }`}
                    >
                      {isHigh ? "A" : isPass ? "B" : "C"}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default QuizHistory;
