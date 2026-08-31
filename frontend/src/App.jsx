import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import AuthModal from './components/AuthModal';
import DocumentManager from './components/DocumentManager';
import ChatInterface from './components/ChatInterface';
import QuizGenerator from './components/QuizGenerator';
import QuizRunner from './components/QuizRunner';
import QuizHistory from './components/QuizHistory';

const MainLayout = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [activeTab, setActiveTab] = useState('documents'); // 'documents' | 'chat' | 'quiz' | 'history'
  const [preselectedDocId, setPreselectedDocId] = useState(null);
  const [activeQuiz, setActiveQuiz] = useState(null);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-3 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mx-auto" />
          <p className="text-xs text-slate-400 font-medium">Initializing StudyGenie...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthModal />;
  }

  const handleSelectChatDoc = (docId) => {
    setPreselectedDocId(docId);
    setActiveTab('chat');
  };

  const handleSelectQuizDoc = (docId) => {
    setPreselectedDocId(docId);
    setActiveQuiz(null);
    setActiveTab('quiz');
  };

  const handleQuizGenerated = (quizData) => {
    setActiveQuiz(quizData);
  };

  const handleResetQuiz = () => {
    setActiveQuiz(null);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500 selection:text-white">
      <Navbar activeTab={activeTab} setActiveTab={(tab) => {
        setActiveTab(tab);
        if (tab === 'quiz') setActiveQuiz(null);
      }} />

      <main className="flex-1">
        {activeTab === 'documents' && (
          <DocumentManager
            onSelectChatDoc={handleSelectChatDoc}
            onSelectQuizDoc={handleSelectQuizDoc}
          />
        )}

        {activeTab === 'chat' && (
          <ChatInterface preselectedDocId={preselectedDocId} />
        )}

        {activeTab === 'quiz' && (
          <>
            {!activeQuiz ? (
              <QuizGenerator
                preselectedDocId={preselectedDocId}
                onQuizGenerated={handleQuizGenerated}
              />
            ) : (
              <QuizRunner
                quiz={activeQuiz}
                onReset={handleResetQuiz}
                onGoToNotes={() => setActiveTab('documents')}
              />
            )}
          </>
        )}

        {activeTab === 'history' && (
          <QuizHistory onStartNewQuiz={() => {
            setActiveQuiz(null);
            setActiveTab('quiz');
          }} />
        )}
      </main>
    </div>
  );
};

function App() {
  return (
    <AuthProvider>
      <MainLayout />
    </AuthProvider>
  );
}

export default App;
