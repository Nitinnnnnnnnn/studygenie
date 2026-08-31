import React, { useState } from 'react';
import {
  CheckCircle2, XCircle, Award, RotateCcw, ArrowRight,
  ArrowLeft, HelpCircle, BookOpen, AlertCircle, ChevronDown, ChevronUp
} from 'lucide-react';
import api from '../api/client';

const QuizRunner = ({ quiz, onReset, onGoToNotes }) => {
  const [currentQuestionIdx, setCurrentQuestionIdx] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState({}); // { question_id: selected_option_index }
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');

  const questions = quiz.questions || [];
  const currentQ = questions[currentQuestionIdx];

  const handleSelectOption = (questionId, optionIndex) => {
    if (results) return; // Prevent changing after submission
    setSelectedAnswers((prev) => ({
      ...prev,
      [questionId]: optionIndex,
    }));
  };

  const handleSubmitQuiz = async () => {
    // Check if any question is unanswered
    const unanswered = questions.filter((q) => selectedAnswers[q.id] === undefined);
    if (unanswered.length > 0) {
      if (!window.confirm(`You have ${unanswered.length} unanswered question(s). Are you sure you want to submit?`)) {
        return;
      }
    }

    setIsSubmitting(true);
    setError('');

    const formattedAnswers = questions.map((q) => ({
      question_id: q.id,
      selected_option_index: selectedAnswers[q.id] !== undefined ? selectedAnswers[q.id] : -1,
    }));

    try {
      const res = await api.post(`/quiz/${quiz.id}/submit`, { answers: formattedAnswers });
      setResults(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit and evaluate quiz.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ================= RESULTS SCREEN =================
  if (results) {
    const isPassing = results.percentage >= 60;

    return (
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        {/* Score Card Header */}
        <div className={`rounded-3xl p-8 border backdrop-blur-sm text-center ${
          isPassing
            ? 'bg-gradient-to-b from-emerald-950/60 to-slate-900 border-emerald-500/30'
            : 'bg-gradient-to-b from-amber-950/60 to-slate-900 border-amber-500/30'
        }`}>
          <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 text-indigo-400 mx-auto flex items-center justify-center mb-4 border border-indigo-500/20 shadow-lg">
            <Award className="w-8 h-8" />
          </div>

          <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider mb-2 bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
            {quiz.difficulty} Difficulty Exam Results
          </span>

          <h2 className="text-4xl font-extrabold text-white">
            {results.score} / {results.total_questions} ({results.percentage}%)
          </h2>
          <p className="text-base text-slate-300 mt-2 font-medium">
            Overall Rating: <span className="text-white font-bold">{results.grade}</span>
          </p>

          <div className="flex justify-center gap-4 mt-6">
            <button
              onClick={onReset}
              className="py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-xl flex items-center gap-2 shadow-lg shadow-indigo-500/20 transition-all"
            >
              <RotateCcw className="w-4 h-4" />
              Generate New Quiz
            </button>
            <button
              onClick={onGoToNotes}
              className="py-2.5 px-5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold rounded-xl flex items-center gap-2 border border-slate-700 transition-all"
            >
              <BookOpen className="w-4 h-4" />
              Review Study Notes
            </button>
          </div>
        </div>

        {/* Detailed Question-by-Question Review */}
        <div className="space-y-6">
          <h3 className="text-xl font-bold text-white flex items-center gap-2">
            <HelpCircle className="w-5 h-5 text-indigo-400" />
            Detailed Answer Explanations
          </h3>

          {results.results.map((qResult, idx) => (
            <div
              key={qResult.question_id}
              className={`p-6 rounded-2xl border transition-all ${
                qResult.is_correct
                  ? 'bg-slate-900/80 border-emerald-500/30'
                  : 'bg-slate-900/80 border-rose-500/30'
              }`}
            >
              {/* Question Header */}
              <div className="flex items-start justify-between gap-3 mb-4">
                <div className="flex items-start gap-3">
                  <span className="w-7 h-7 rounded-lg bg-slate-800 text-slate-300 flex items-center justify-center text-xs font-bold flex-shrink-0 border border-slate-700">
                    {idx + 1}
                  </span>
                  <h4 className="text-base font-semibold text-white leading-relaxed">
                    {qResult.question_text}
                  </h4>
                </div>

                {qResult.is_correct ? (
                  <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold flex-shrink-0">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Correct
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-bold flex-shrink-0">
                    <XCircle className="w-3.5 h-3.5" /> Incorrect
                  </span>
                )}
              </div>

              {/* Options Breakdown */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4">
                {qResult.options.map((optText, oIdx) => {
                  const isCorrectAnswer = oIdx === qResult.correct_option_index;
                  const isUserSelection = oIdx === qResult.selected_option_index;

                  let optClass = 'bg-slate-800/50 border-slate-700/60 text-slate-400';
                  if (isCorrectAnswer) {
                    optClass = 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300 font-semibold';
                  } else if (isUserSelection && !qResult.is_correct) {
                    optClass = 'bg-rose-500/15 border-rose-500/40 text-rose-300 font-semibold';
                  }

                  return (
                    <div
                      key={oIdx}
                      className={`p-3 rounded-xl border text-xs flex items-center justify-between ${optClass}`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="w-5 h-5 rounded-md bg-slate-800/80 flex items-center justify-center text-[10px] font-bold">
                          {String.fromCharCode(65 + oIdx)}
                        </span>
                        <span>{optText}</span>
                      </div>
                      {isCorrectAnswer && <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />}
                      {isUserSelection && !qResult.is_correct && (
                        <XCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Educational Explanation Box */}
              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-xs leading-relaxed text-slate-300">
                <p className="font-bold text-indigo-400 mb-1 flex items-center gap-1.5">
                  <BookOpen className="w-3.5 h-3.5" />
                  Answer Explanation:
                </p>
                {qResult.explanation}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ================= ACTIVE TEST SCREEN =================
  if (!currentQ) {
    return <div className="text-center py-12 text-slate-400">No questions available.</div>;
  }

  const selectedForCurrent = selectedAnswers[currentQ.id];
  const progressPct = ((currentQuestionIdx + 1) / questions.length) * 100;
  const answeredCount = Object.keys(selectedAnswers).length;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 sm:p-8 backdrop-blur-sm shadow-2xl space-y-6">
        {/* Top Progress & Stats */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="text-indigo-400">
              Question {currentQuestionIdx + 1} of {questions.length}
            </span>
            <span className="text-slate-400">
              {answeredCount} of {questions.length} answered
            </span>
          </div>

          <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-300"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Question Text */}
        <div className="py-2">
          <h3 className="text-lg font-bold text-white leading-relaxed">
            {currentQ.question_text}
          </h3>
        </div>

        {/* Options List */}
        <div className="space-y-3">
          {currentQ.options.map((optText, oIdx) => {
            const isSelected = selectedForCurrent === oIdx;
            return (
              <div
                key={oIdx}
                onClick={() => handleSelectOption(currentQ.id, oIdx)}
                className={`p-4 rounded-2xl border cursor-pointer transition-all flex items-center justify-between ${
                  isSelected
                    ? 'bg-indigo-600/20 border-indigo-500 text-white font-semibold shadow-lg shadow-indigo-500/10'
                    : 'bg-slate-800/50 border-slate-700/80 text-slate-300 hover:bg-slate-800 hover:border-slate-600'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className={`w-8 h-8 rounded-xl flex items-center justify-center text-xs font-bold ${
                    isSelected ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-400'
                  }`}>
                    {String.fromCharCode(65 + oIdx)}
                  </span>
                  <span className="text-sm">{optText}</span>
                </div>

                {isSelected && <CheckCircle2 className="w-5 h-5 text-indigo-400" />}
              </div>
            );
          })}
        </div>

        {/* Navigation & Submit Bar */}
        <div className="flex items-center justify-between pt-6 border-t border-slate-800">
          <button
            type="button"
            disabled={currentQuestionIdx === 0}
            onClick={() => setCurrentQuestionIdx((prev) => Math.max(0, prev - 1))}
            className="py-2.5 px-4 bg-slate-800 hover:bg-slate-700 disabled:opacity-30 text-slate-300 text-xs font-semibold rounded-xl flex items-center gap-1.5 transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
            Previous
          </button>

          {currentQuestionIdx < questions.length - 1 ? (
            <button
              type="button"
              onClick={() => setCurrentQuestionIdx((prev) => Math.min(questions.length - 1, prev + 1))}
              className="py-2.5 px-5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl flex items-center gap-1.5 transition-all shadow-lg shadow-indigo-500/20"
            >
              Next Question
              <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              disabled={isSubmitting}
              onClick={handleSubmitQuiz}
              className="py-2.5 px-6 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold rounded-xl flex items-center gap-2 shadow-lg shadow-emerald-500/25 transition-all"
            >
              {isSubmitting ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  Submit Exam
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default QuizRunner;
