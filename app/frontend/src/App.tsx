import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  FileText,
  CheckCircle,
  XCircle,
  AlertCircle,
  Search,
  ArrowRight,
  MessageSquare,
  Download
} from 'lucide-react';
import { api } from './lib/api';

// Components
const StatCard = ({ title, value, icon: Icon, color }: any) => (
  <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 flex items-center gap-4">
    <div className={`p-3 rounded-lg ${color}`}>
      <Icon className="w-6 h-6 text-white" />
    </div>
    <div>
      <p className="text-sm text-slate-500 font-medium">{title}</p>
      <h3 className="text-2xl font-bold text-slate-900">{value}</h3>
    </div>
  </div>
);

const ReasoningLog = ({ text }: { text: string }) => {
  if (!text) return <div className="text-xs text-slate-400 italic">No reasoning captured for this report.</div>;

  const entries = text.split('\\n').filter(line => line.trim());

  return (
    <div className="flex flex-col gap-2 py-2">
      {entries.map((entry, i) => {
        const [role, ...contentParts] = entry.split(': ');
        const content = contentParts.join(': ');

        let bgColor = 'bg-slate-100 text-slate-600';
        let label = role || 'System';
        let icon = <MessageSquare className="w-3 h-3" />;

        if (role === 'assistant') {
          bgColor = 'bg-indigo-50 text-indigo-700 border-indigo-100';
          label = 'AI Agent';
        } else if (role === 'tool') {
          bgColor = 'bg-amber-50 text-amber-700 border-amber-100';
          label = 'Tool Call';
        } else if (role === 'tool_result') {
          bgColor = 'bg-emerald-50 text-emerald-700 border-emerald-100';
          label = 'Tool Result';
        }

        return (
          <div key={i} className={`p-2 rounded-md border text-xs font-mono ${bgColor}`}>
            <div className="flex items-center gap-2 mb-1 font-bold uppercase text-[10px] opacity-70">
              {icon}
              <span>{label}</span>
            </div>
            <div className="whitespace-pre-wrap break-words leading-relaxed">
              {content}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const ReportRow = ({ report, onUpdate }: any) => {
  const [isUpdating, setIsUpdating] = useState(false);
  const [showReasoning, setShowReasoning] = useState(false);
  const [correctionNote, setCorrectionNote] = useState('');

  const handleStatusChange = async (status: string) => {
    setIsUpdating(true);
    try {
      await api.patch(`/reports/${report.id}`, {
        status,
        note: status === 'REJECTED' ? correctionNote : null
      });
      await onUpdate();
    } catch (e) {
      alert("Failed to update report");
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <>
      <tr className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
        <td className="p-4 text-sm font-medium text-slate-900">{report.vendor_name}</td>
        <td className="p-4 text-sm text-slate-600">{report.vendor_id}</td>
        <td className="p-4 text-sm text-slate-600">₹{report.invoice_amount?.toLocaleString() || '0'}</td>
        <td className="p-4 text-sm text-slate-600">{report.days_late} days</td>
        <td className="p-4 text-sm text-slate-900 font-semibold">₹{report.penalty_amount?.toLocaleString()}</td>
        <td className="p-4">
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
            report.status === 'PENDING' ? 'bg-amber-100 text-amber-700' :
            report.status === 'APPROVED' ? 'bg-emerald-100 text-emerald-700' :
            'bg-rose-100 text-rose-700'
          }`}>
            {report.status}
          </span>
        </td>
        <td className="p-4">
          <button
            onClick={() => setShowReasoning(!showReasoning)}
            className="flex items-center gap-2 text-xs text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
          >
            <MessageSquare className="w-4 h-4" />
            {showReasoning ? 'Hide Reasoning' : 'View Reasoning'}
          </button>
        </td>
        <td className="p-4 text-right">
          {report.status === 'PENDING' && (
            <div className="flex justify-end gap-2">
              <button
                onClick={() => handleStatusChange('APPROVED')}
                disabled={isUpdating}
                className="p-1 text-emerald-600 hover:bg-emerald-50 rounded transition-colors"
                title="Approve"
              >
                <CheckCircle className="w-5 h-5" />
              </button>
              <button
                onClick={() => setShowReasoning(true)}
                disabled={isUpdating}
                className="p-1 text-rose-600 hover:bg-rose-50 rounded transition-colors"
                title="Reject with Note"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>
          )}
        </td>
      </tr>
      {showReasoning && (
        <tr className="bg-slate-50">
          <td colSpan={8} className="p-4 border-b border-slate-200">
            <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
              <div className="flex justify-between items-center mb-3">
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Agent Reasoning Chain</h4>
                {report.status === 'PENDING' && (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Add correction note..."
                      value={correctionNote}
                      onChange={(e) => setCorrectionNote(e.target.value)}
                      className="text-xs p-2 border border-slate-200 rounded-md outline-none focus:ring-2 focus:ring-indigo-500 w-64"
                    />
                    <button
                      onClick={() => handleStatusChange('REJECTED')}
                      disabled={isUpdating}
                      className="bg-rose-600 text-white text-xs px-3 py-1 rounded-md hover:bg-rose-700 transition-colors"
                    >
                      Confirm Rejection
                    </button>
                  </div>
                )}
              </div>
              <ReasoningLog text={report.agent_reasoning} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
};

function App() {
  const [reports, setReports] = useState([]);
  const [vendorName, setVendorName] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchReports = async () => {
    const data = await api.get('/reports');
    setReports(data);
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const runAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vendorName) return;
    setLoading(true);
    try {
      await api.post(`/audit/${vendorName}`);
      setVendorName('');
      await fetchReports();
    } catch (e) {
      alert("Audit failed to start");
    } finally {
      setLoading(false);
    }
  };

  const exportSettlement = async () => {
    try {
      window.open('http://localhost:8000/export/settlement', '_blank');
    } catch (e) {
      alert("Export failed");
    }
  };

  const pendingCount = reports.filter((r: any) => r.status === 'PENDING').length;
  const approvedCount = reports.filter((r: any) => r.status === 'APPROVED').length;
  const totalRecoverable = reports
    .filter((r: any) => r.status === 'APPROVED')
    .reduce((acc: number, curr: any) => acc + curr.penalty_amount, 0);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Sidebar */}
      <div className="fixed left-0 top-0 h-full w-64 bg-slate-900 text-white p-6 flex flex-col gap-8">
        <div className="flex items-center gap-3 px-2">
          <div className="bg-indigo-500 p-2 rounded-lg">
            <FileText className="w-6 h-6 text-white" />
          </div>
          <h1 className="font-bold text-lg tracking-tight">AuditAI</h1>
        </div>

        <nav className="flex flex-col gap-2">
          <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg bg-indigo-600 text-white transition-colors">
            <LayoutDashboard className="w-5 h-5" />
            <span className="font-medium">Dashboard</span>
          </a>
        </nav>
      </div>

      {/* Main Content */}
      <main className="pl-64 p-8">
        <header className="flex justify-between items-center mb-8">
          <div>
            <h2 className="text-3xl font-bold text-slate-900">Audit Overview</h2>
            <p className="text-slate-500">Manage and approve financial discrepancies</p>
          </div>

          <form onSubmit={runAudit} className="flex gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Enter vendor name..."
                value={vendorName}
                onChange={(e) => setVendorName(e.target.value)}
                className="pl-10 pr-4 py-2 rounded-lg border border-slate-200 focus:ring-2 focus:ring-indigo-500 outline-none w-64 transition-all"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="bg-indigo-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {loading ? "Auditing..." : "Run Audit"}
              {!loading && <ArrowRight className="w-4 h-4" />}
            </button>
          </form>
        </header>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <StatCard
            title="Pending Review"
            value={pendingCount}
            icon={AlertCircle}
            color="bg-amber-500"
          />
          <StatCard
            title="Approved Findings"
            value={approvedCount}
            icon={CheckCircle}
            color="bg-emerald-500"
          />
          <StatCard
            title="Total Recoverable"
            value={`₹${totalRecoverable.toLocaleString()}`}
            icon={FileText}
            color="bg-indigo-500"
          />
        </div>

        {/* Reports Table */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-6 border-b border-slate-100 flex justify-between items-center">
            <h3 className="font-bold text-slate-900">Discrepancy Queue</h3>
            <button
              onClick={exportSettlement}
              className="flex items-center gap-2 bg-white border border-slate-200 text-slate-600 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-slate-50 transition-colors shadow-sm"
            >
              <Download className="w-4 h-4" />
              Export Settlement Sheet
            </button>
          </div>
          <table className="w-full text-left">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider">
              <tr>
                <th className="p-4 font-semibold">Vendor</th>
                <th className="p-4 font-semibold">ID</th>
                <th className="p-4 font-semibold">Invoice Amt</th>
                <th className="p-4 font-semibold">Days Late</th>
                <th className="p-4 font-semibold">Penalty</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold">Agent Logic</th>
                <th className="p-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-slate-400 italic">
                    No audit reports found. Start by running an audit for a vendor.
                  </td>
                </tr>
              ) : (
                reports.map((report: any) => (
                  <ReportRow key={report.id} report={report} onUpdate={fetchReports} />
                ))
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}

export default App;
