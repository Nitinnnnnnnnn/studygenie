import React from 'react';
import { Sparkles, BookOpen, MessageSquare, HelpCircle, History, LogOut, User as UserIcon } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Navbar = ({ activeTab, setActiveTab }) => {
  const { user, logout } = useAuth();

  const navItems = [
    { id: 'documents', label: 'Study Notes', icon: BookOpen },
    { id: 'chat', label: 'RAG Q&A Chat', icon: MessageSquare },
    { id: 'quiz', label: 'AI Quiz Prep', icon: HelpCircle },
    { id: 'history', label: 'Attempt History', icon: History },
  ];

  return (
    <header className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur-md border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab('documents')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="text-xl font-bold bg-gradient-to-r from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">
                StudyGenie
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                RAG + Mistral AI
              </span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                    isActive
                      ? 'bg-indigo-600/15 text-indigo-400 border border-indigo-500/30 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-400' : 'text-slate-400'}`} />
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* User Profile & Logout */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/50">
              <div className="w-7 h-7 rounded-full bg-indigo-600/30 text-indigo-300 flex items-center justify-center text-xs font-bold border border-indigo-500/30">
                {user?.full_name ? user.full_name[0].toUpperCase() : 'U'}
              </div>
              <div className="text-left">
                <p className="text-xs font-semibold text-slate-200 truncate max-w-[120px]">{user?.full_name || 'Student'}</p>
                <p className="text-[10px] text-slate-400 truncate max-w-[120px]">{user?.email}</p>
              </div>
            </div>

            <button
              onClick={logout}
              title="Sign Out"
              className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Tab Bar */}
      <div className="flex md:hidden border-t border-slate-800/80 px-2 py-1 bg-slate-900/90 overflow-x-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`flex-1 flex flex-col items-center py-1.5 px-2 rounded-lg text-[11px] font-medium ${
                isActive ? 'text-indigo-400 bg-indigo-500/10' : 'text-slate-400'
              }`}
            >
              <Icon className="w-4 h-4 mb-0.5" />
              {item.label}
            </button>
          );
        })}
      </div>
    </header>
  );
};

export default Navbar;
