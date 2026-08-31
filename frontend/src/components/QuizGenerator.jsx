import React, { useState, useEffect } from 'react';
import { Sparkles, HelpCircle, FileText, CheckCircle2, AlertCircle, ArrowRight, Zap, Target, Flame } from 'lucide-react';
import api from '../api/client';

const QuizGenerator = ({ preselectedDocId, onQuizGenerated }) => {
  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(preselectedDocId || '');
  const [difficulty, setDifficulty] = useState('Medium');
  const [questionCount, setQuestionCount] = useState(5);
  const [topic, setTopic] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDocs = async () => {
      try {
        const res = await api.get('/documents/');
        setDocuments(res.data);
        if (res.data.length > 0 && !selectedDocId) {
          setSelectedDocId(res.data[0].id);
        }
      } catch (err) {
        console.error('Failed to load documents', err);
      }
    };
    fetchDocs();
  }, []);

  useEffect(() => {
    if (preselectedDocId) {
      setSelectedDocId(preselectedDocId);
    }
  }, [preselectedDocId]);

  const handleGenerateQuiz = async (e) => {
    e.preventDefault();
    setError('');
    setIsGenerating(true);

    try {
      const res = await api.post('/quiz/generate', {
        document_id: selectedDocId ? parseInt(selectedDocId, 10) : null,
        difficulty,
        total_questions: questionCount,
        topic: topic.trim() || null,
      });

      if (onQuizGenerated) {
        onQuizGenerated(res.data);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate quiz. Make sure study notes are uploaded.');
    } finally {
      setIsGenerating(false);
    }
  };

  const difficulties = [
    {
      id: 'Easy',
      title: 'Easy',
      icon: Zap,
      desc: 'Definitions, core facts, and direct recall from the notes.',
      color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
    },
    {
      id: 'Medium',
      title: 'Medium',
      icon: Target,
      desc: 'Conceptual understanding, comparing ideas, and core application.',
      color: 'text-indigo-400 border-indigo-500/30 bg-indigo-500/10',
    },
    {
      id: 'Hard',
      title: 'Hard',
      icon: Flame,
      desc: 'In-depth analysis, scenario reasoning, and complex edge cases.',
      color: 'text-rose-400 border-rose-500/30 bg-rose-500/10',
    },
  ];

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-6 sm:p-10 backdrop-blur-sm shadow-2xl">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <HelpCircle className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white tracking-tight">AI Interactive Quiz Generator</h2>
            <p className="text-sm text-slate-400">Generate targeted practice MCQs grounded strictly in your study material.</p>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-3 p-4 mb-6 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleGenerateQuiz} className="space-y-6">
          {/* Step 1: Select Document */}
          <div>
            <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
              1. Select Study Material
            </label>
            {documents.length === 0 ? (
              <div className="p-4 bg-slate-800/60 border border-slate-700/80 rounded-2xl text-sm text-slate-400 text-center">
                No documents uploaded yet. Please upload a PDF in the <strong>Study Notes</strong> tab first!
              </div>
            ) : (
              <select
                value={selectedDocId}
                onChange={(e) => setSelectedDocId(e.target.value)}
                className="w-full bg-slate-800/80 border border-slate-700/80 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500"
              >
                <option value="">📚 All Uploaded Study Notes</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    📄 {d.filename} ({d.total_pages} Pages)
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Step 2: Difficulty Level */}
          <div>
            <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
              2. Choose Difficulty Level
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {difficulties.map((d) => {
                const Icon = d.icon;
                const isSelected = difficulty === d.id;
                return (
                  <div
                    key={d.id}
                    onClick={() => setDifficulty(d.id)}
                    className={`p-4 rounded-2xl border cursor-pointer transition-all ${
                      isSelected
                        ? `${d.color} border-2 shadow-lg`
                        : 'border-slate-800 bg-slate-800/40 hover:bg-slate-800/80 text-slate-400'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2 font-bold text-sm text-white">
                        <Icon className="w-4 h-4" />
                        <span>{d.title}</span>
                      </div>
                      {isSelected && <CheckCircle2 className="w-4 h-4 text-indigo-400" />}
                    </div>
                    <p className="text-xs text-slate-400 leading-snug">{d.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Step 3: Question Count */}
          <div>
            <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
              3. Number of Questions
            </label>
            <div className="flex gap-3">
              {[5, 10, 20].map((count) => (
                <button
                  type="button"
                  key={count}
                  onClick={() => setQuestionCount(count)}
                  className={`flex-1 py-3 rounded-xl text-sm font-bold border transition-all ${
                    questionCount === count
                      ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-500/25'
                      : 'bg-slate-800/50 border-slate-700/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  {count} Questions
                </button>
              ))}
            </div>
          </div>

          {/* Step 4: Optional Topic Focus */}
          <div>
            <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
              4. Specific Topic / Chapter (Optional)
            </label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Memory Hierarchy, Neural Networks, Dynamic Programming..."
              className="w-full bg-slate-800/80 border border-slate-700/80 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isGenerating || documents.length === 0}
            className="w-full py-4 px-6 bg-gradient-to-r from-indigo-600 via-purple-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-bold text-base rounded-2xl shadow-xl shadow-indigo-500/25 flex items-center justify-center gap-3 transition-all disabled:opacity-40"
          >
            {isGenerating ? (
              <>
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Reading Notes & Crafting {questionCount} {difficulty} Questions...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5" />
                <span>Generate {difficulty} Quiz ({questionCount} MCQs)</span>
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};

export default QuizGenerator;
