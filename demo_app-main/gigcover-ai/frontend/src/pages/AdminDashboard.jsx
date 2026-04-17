import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'
import { Bar, Line, Pie } from 'react-chartjs-2'
import { api } from '../api'
import { AnimatedTransactionCard, PLATFORM_CONFIGS } from '../components/dashboard/AnimatedTransactions'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Tooltip, Legend)

export default function AdminDashboard() {
  const [data, setData] = useState(null)
  const [settings, setSettings] = useState({ rainfall_threshold: 100, risk_weight: 1.0, disruption_type: 'Rainfall' })
  const [message, setMessage] = useState('')

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const response = await api.get('/dashboard-data')
        if (mounted) setData(response.data)
      } catch (error) {
        console.error('Error loading dashboard:', error)
      }
    })()

    return () => {
      mounted = false
    }
  }, [])

  const saveSettings = async () => {
    try {
      await api.post('/admin/settings', settings)
      setMessage('Settings updated successfully.')
      setTimeout(() => setMessage(''), 3000)
    } catch (error) {
      setMessage('Error updating settings.')
    }
  }

  const chartData = useMemo(() => {
    const risks = data?.risks || []
    return {
      labels: risks.map((item) => `U${item.user_id}`),
      datasets: [
        {
          label: 'Risk Score',
          data: risks.map((item) => item.risk_score),
          borderColor: '#a78bfa',
          backgroundColor: '#93c5fd',
          tension: 0.35,
        },
      ],
    }
  }, [data])

  const payoutsData = useMemo(() => {
    const claims = data?.claims || []
    return {
      labels: claims.map((claim) => claim.claim_id),
      datasets: [
        {
          label: 'Payout Amount',
          data: claims.map((claim) => claim.payout),
          backgroundColor: '#86efac',
        },
      ],
    }
  }, [data])

  if (!data) {
    return <div className="px-8 py-16 text-slate-700">Loading admin panel...</div>
  }

  return (
    <div className="mx-auto max-w-7xl px-4 pb-12 pt-8">
      {message && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          className="glass mb-4 rounded-2xl p-4 text-sm text-green-600 font-semibold"
        >
          ✅ {message}
        </motion.div>
      )}

      {/* Header with animation */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          Admin Dashboard
        </h1>
        <p className="text-slate-600 mt-2">Monitor system performance, fraud detection, and predictive analytics</p>
      </motion.div>

      {/* Animated Key Metrics */}
      <div className="grid gap-4 md:grid-cols-4 mb-8">
        {[
          { title: 'Total Users', value: data.analytics.total_users, icon: '👥', color: 'from-blue-400 to-blue-600' },
          { title: 'Total Claims', value: data.analytics.total_claims, icon: '📋', color: 'from-purple-400 to-purple-600' },
          { title: 'Total Payouts', value: `₹${Number(data.analytics.total_payouts).toFixed(0)}`, icon: '💰', color: 'from-green-400 to-green-600' },
          { title: 'Fraud Detected', value: data.analytics.fraud_alerts || 0, icon: '🛡️', color: 'from-red-400 to-red-600' },
        ].map((metric, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.1 }}
            whileHover={{ scale: 1.05 }}
            className={`bg-gradient-to-r ${metric.color} rounded-2xl p-6 text-white shadow-lg`}
          >
            <div className="text-3xl mb-2">{metric.icon}</div>
            <p className="text-sm font-medium opacity-90">{metric.title}</p>
            <p className="text-3xl font-bold mt-2">{metric.value}</p>
          </motion.div>
        ))}
      </div>

      {/* Charts and Analytics */}
      <div className="grid gap-6 xl:grid-cols-2 mb-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass rounded-3xl p-6"
        >
          <h2 className="font-outfit text-2xl font-semibold text-slate-800 mb-4">📊 Risk Score Trend</h2>
          <div className="bg-white/50 rounded-xl p-4">
            <Line data={chartData} options={{ responsive: true, maintainAspectRatio: true }} />
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="glass rounded-3xl p-6"
        >
          <h2 className="font-outfit text-2xl font-semibold text-slate-800 mb-4">💸 Claim Payouts</h2>
          <div className="bg-white/50 rounded-xl p-4">
            <Bar data={payoutsData} options={{ responsive: true, maintainAspectRatio: true }} />
          </div>
        </motion.div>
      </div>

      {/* Platform Distribution */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="glass rounded-3xl p-6 mb-8"
      >
        <h3 className="font-outfit text-xl font-semibold text-slate-800 mb-4">🚀 Platform Activity Distribution</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {Object.entries(PLATFORM_CONFIGS).map(([platform, config], i) => (
            <motion.div
              key={platform}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.4 + i * 0.05 }}
              whileHover={{ scale: 1.1, rotate: 5 }}
              className={`bg-gradient-to-r ${config.gradient} rounded-xl p-4 text-white text-center shadow-md cursor-pointer`}
            >
              <div className="text-3xl mb-2">{config.emoji}</div>
              <p className="font-semibold text-sm">{platform}</p>
              <motion.p
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ repeat: Infinity, duration: 2 }}
                className="text-xs opacity-75 mt-1"
              >
                Active
              </motion.p>
            </motion.div>
          ))}
        </div>
      </motion.div>

      <div className="grid gap-6 xl:grid-cols-2">
        {/* Admin Controls */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5 }}
          className="glass rounded-3xl p-6"
        >
          <h3 className="font-space text-lg font-semibold text-slate-800 mb-4">⚙️ System Configuration</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-slate-700 font-semibold mb-2">Add New Disruption Type</label>
              <input
                className="w-full bg-white/50 border border-white/30 rounded-xl px-4 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-purple-400"
                value={settings.disruption_type}
                onChange={(e) => setSettings((prev) => ({ ...prev, disruption_type: e.target.value }))}
                placeholder="e.g., Rainfall"
              />
            </div>

            <div>
              <label className="block text-sm text-slate-700 font-semibold mb-2">Rainfall Threshold (mm)</label>
              <input
                type="number"
                className="w-full bg-white/50 border border-white/30 rounded-xl px-4 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-purple-400"
                value={settings.rainfall_threshold}
                onChange={(e) => setSettings((prev) => ({ ...prev, rainfall_threshold: Number(e.target.value) }))}
              />
            </div>

            <div>
              <label className="block text-sm text-slate-700 font-semibold mb-2">Risk Weight Multiplier</label>
              <input
                type="number"
                step="0.1"
                className="w-full bg-white/50 border border-white/30 rounded-xl px-4 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-purple-400"
                value={settings.risk_weight}
                onChange={(e) => setSettings((prev) => ({ ...prev, risk_weight: Number(e.target.value) }))}
              />
            </div>

            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={saveSettings}
              className="w-full bg-gradient-to-r from-purple-500 to-blue-600 text-white font-semibold py-3 rounded-xl hover:from-purple-600 hover:to-blue-700 transition-all shadow-lg"
            >
              💾 Save Configuration
            </motion.button>
          </div>
        </motion.div>

        {/* Live Records */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5 }}
          className="glass rounded-3xl p-6"
        >
          <h3 className="font-space text-lg font-semibold text-slate-800 mb-4">📋 Live Activity</h3>
          
          {/* Users Section */}
          <div className="mb-6">
            <p className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-2">
              <span className="text-lg">👥</span> Active Users ({(data.users || []).length})
            </p>
            <div className="max-h-32 overflow-y-auto rounded-xl bg-gradient-to-r from-blue-50 to-purple-50 p-3 space-y-2">
              <AnimatePresence>
                {(data.users || []).slice(0, 5).map((user, i) => (
                  <motion.p
                    key={user.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="text-xs text-slate-700 p-2 bg-white/50 rounded-lg border border-white/20"
                  >
                    <span className="font-semibold">{user.name}</span> • {user.role}
                  </motion.p>
                ))}
              </AnimatePresence>
            </div>
          </div>

          {/* Claims Section */}
          <div>
            <p className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-2">
              <span className="text-lg">📋</span> Recent Claims ({(data.claims || []).length})
            </p>
            <div className="max-h-32 overflow-y-auto rounded-xl bg-gradient-to-r from-green-50 to-emerald-50 p-3 space-y-2">
              <AnimatePresence>
                {(data.claims || []).slice(0, 5).map((claim, i) => (
                  <motion.p
                    key={claim.claim_id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="text-xs text-slate-700 p-2 bg-white/50 rounded-lg border border-white/20"
                  >
                    <span className="font-semibold">{claim.claim_id}</span> • ₹{Number(claim.payout).toFixed(0)} • {claim.trigger_type}
                  </motion.p>
                ))}
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

function Metric({ title, value }) {
  return (
    <div className="rounded-2xl bg-gradient-to-r from-[#c4b5fd] via-[#bfdbfe] to-[#bbf7d0] p-5 shadow-md transition duration-300 hover:shadow-lg">
      <p className="text-sm text-slate-600">{title}</p>
      <p className="font-outfit text-3xl font-bold text-slate-800">{value}</p>
    </div>
  )
}
