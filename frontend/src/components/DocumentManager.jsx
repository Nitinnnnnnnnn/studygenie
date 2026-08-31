import React, { useState, useEffect } from 'react';
import { UploadCloud, FileText, Trash2, CheckCircle, AlertCircle, Layers, Calendar, ArrowRight, Sparkles, MessageSquare, HelpCircle } from 'lucide-react';
import api from '../api/client';

const DocumentManager = ({ onSelectChatDoc, onSelectQuizDoc }) => {
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [dragActive, setDragActive] = useState(false);

  const fetchDocuments = async () => {
    try {
      setIsLoading(true);
      const res = await api.get('/documents/');
      setDocuments(res.data);
    } catch (err) {
      console.error('Failed to load documents', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleFileUpload = async (files) => {
    if (!files || files.length === 0) return;

    setUploadError('');
    setUploadSuccess('');
    setIsUploading(true);

    const formData = new FormData();
    let validCount = 0;
    for (let i = 0; i < files.length; i++) {
      if (files[i].name.toLowerCase().endsWith('.pdf')) {
        formData.append('files', files[i]);
        validCount++;
      }
    }

    if (validCount === 0) {
      setUploadError('Please select valid PDF documents.');
      setIsUploading(false);
      return;
    }

    try {
      const res = await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setUploadSuccess(`Successfully processed and indexed ${res.data.documents.length} PDF note(s)!`);
      fetchDocuments();
    } catch (err) {
      setUploadError(err.response?.data?.detail || 'Failed to upload and process PDF documents.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (docId, filename) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}" and its vector embeddings?`)) {
      return;
    }

    try {
      await api.delete(`/documents/${docId}`);
      setDocuments(documents.filter((d) => d.id !== docId));
    } catch (err) {
      alert('Failed to delete document.');
    }
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-indigo-900/40 via-purple-900/30 to-slate-900 border border-indigo-500/20 rounded-3xl p-8 backdrop-blur-sm">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold mb-3">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Document Ingestion & ChromaDB Vector Store</span>
          </div>
          <h2 className="text-3xl font-extrabold text-white tracking-tight">Upload Your Course Notes & Textbooks</h2>
          <p className="text-slate-300 mt-2 text-base leading-relaxed">
            Upload single or multiple PDF documents. StudyGenie automatically parses page texts, calculates semantic chunks, generates Mistral embeddings, and synchronizes with the ChromaDB vector database for RAG Q&A and AI quizzes.
          </p>
        </div>
      </div>

      {/* Upload Zone */}
      <div
        onDragEnter={() => setDragActive(true)}
        onDragLeave={() => setDragActive(false)}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          if (e.dataTransfer.files) handleFileUpload(e.dataTransfer.files);
        }}
        className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all ${
          dragActive
            ? 'border-indigo-500 bg-indigo-500/10'
            : 'border-slate-700/80 bg-slate-900/60 hover:border-indigo-500/50 hover:bg-slate-900/90'
        }`}
      >
        <input
          type="file"
          id="pdf-upload"
          multiple
          accept=".pdf"
          className="hidden"
          onChange={(e) => handleFileUpload(e.target.files)}
          disabled={isUploading}
        />
        <label htmlFor="pdf-upload" className="cursor-pointer block">
          <div className="w-16 h-16 rounded-2xl bg-indigo-600/20 text-indigo-400 mx-auto flex items-center justify-center mb-4 border border-indigo-500/30">
            {isUploading ? (
              <div className="w-8 h-8 border-3 border-indigo-400/30 border-t-indigo-400 rounded-full animate-spin" />
            ) : (
              <UploadCloud className="w-8 h-8" />
            )}
          </div>
          <h3 className="text-lg font-bold text-white">
            {isUploading ? 'Extracting, Chunking & Indexing...' : 'Click to Upload or Drag & Drop Multiple PDFs'}
          </h3>
          <p className="text-sm text-slate-400 mt-1">Supports multi-page course notes, syllabus, chapters, and academic slides (.PDF)</p>
          <span className="inline-block mt-4 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-500/25 transition-all">
            Browse PDF Files
          </span>
        </label>
      </div>

      {/* Upload Alerts */}
      {uploadError && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{uploadError}</span>
        </div>
      )}
      {uploadSuccess && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm">
          <CheckCircle className="w-5 h-5 flex-shrink-0" />
          <span>{uploadSuccess}</span>
        </div>
      )}

      {/* Uploaded Documents List */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-bold text-white flex items-center gap-2">
            <FileText className="w-5 h-5 text-indigo-400" />
            Your Indexed Knowledge Base ({documents.length})
          </h3>
          <button
            onClick={fetchDocuments}
            className="text-xs text-slate-400 hover:text-indigo-400 transition-colors font-medium"
          >
            Refresh
          </button>
        </div>

        {isLoading ? (
          <div className="text-center py-12 text-slate-500">Loading your knowledge base...</div>
        ) : documents.length === 0 ? (
          <div className="text-center py-12 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
            <FileText className="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400 font-medium">No study materials uploaded yet.</p>
            <p className="text-xs text-slate-500 mt-1">Upload your first syllabus or chapter PDF above to get started!</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="bg-slate-900/80 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 backdrop-blur-sm transition-all flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center flex-shrink-0 border border-indigo-500/20">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-white line-clamp-1 group-hover:text-indigo-300 transition-colors">
                          {doc.filename}
                        </h4>
                        <p className="text-xs text-slate-400 mt-0.5">{formatBytes(doc.file_size)}</p>
                      </div>
                    </div>

                    <button
                      onClick={() => handleDelete(doc.id, doc.filename)}
                      title="Delete from Vector DB & Disk"
                      className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Metadata Chips */}
                  <div className="flex flex-wrap gap-2 mt-4 text-xs">
                    <span className="px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1.5 font-medium">
                      <FileText className="w-3.5 h-3.5 text-indigo-400" />
                      {doc.total_pages} Pages
                    </span>
                    <span className="px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1.5 font-medium">
                      <Layers className="w-3.5 h-3.5 text-violet-400" />
                      {doc.chunk_count} Vector Chunks
                    </span>
                    <span className="px-2.5 py-1 rounded-lg bg-slate-800/60 text-slate-400 border border-slate-700/50 flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5" />
                      {new Date(doc.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                {/* Action Shortcuts */}
                <div className="flex items-center gap-2 mt-5 pt-4 border-t border-slate-800/80">
                  <button
                    onClick={() => onSelectChatDoc && onSelectChatDoc(doc.id)}
                    className="flex-1 py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-indigo-600/20 text-slate-300 hover:text-indigo-300 border border-slate-700 hover:border-indigo-500/40 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all"
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    Ask Doubts (RAG)
                  </button>
                  <button
                    onClick={() => onSelectQuizDoc && onSelectQuizDoc(doc.id)}
                    className="flex-1 py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-violet-600/20 text-slate-300 hover:text-violet-300 border border-slate-700 hover:border-violet-500/40 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all"
                  >
                    <HelpCircle className="w-3.5 h-3.5" />
                    Generate Quiz
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentManager;
