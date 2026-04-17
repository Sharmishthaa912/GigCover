import { motion } from 'framer-motion'

// Platform logos and colors
const PLATFORM_CONFIGS = {
  'Swiggy': { emoji: '🍔', color: '#FFA500', gradient: 'from-orange-400 to-orange-600' },
  'Zomato': { emoji: '🍕', color: '#E03546', gradient: 'from-red-400 to-red-600' },
  'Blinkit': { emoji: '⚡', color: '#FFD700', gradient: 'from-yellow-300 to-yellow-500' },
  'Zepto': { emoji: '🚀', color: '#9400FF', gradient: 'from-purple-400 to-purple-600' },
  'Uber': { emoji: '🚗', color: '#000000', gradient: 'from-slate-700 to-black' },
  'Dunzo': { emoji: '📦', color: '#FF6B9D', gradient: 'from-pink-400 to-pink-600' },
  'Flipkart': { emoji: '📱', color: '#1e40af', gradient: 'from-blue-500 to-blue-700' },
  'Amazon': { emoji: '📦', color: '#FF9900', gradient: 'from-amber-400 to-amber-600' },
  'Other': { emoji: '💼', color: '#6B7280', gradient: 'from-gray-400 to-gray-600' }
}

const AnimatedPlatformLogo = ({ platform, amount, status, delay = 0 }) => {
  const config = PLATFORM_CONFIGS[platform] || PLATFORM_CONFIGS['Other']

  const statusConfig = {
    Success: { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-700', icon: '✅' },
    Failed: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', icon: '❌' },
    Pending: { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-700', icon: '⏳' }
  }

  const cfg = statusConfig[status] || statusConfig['Pending']

  return (
    <motion.div
      initial={{ opacity: 0, x: -50 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay }}
      className={`${cfg.bg} rounded-2xl border-2 ${cfg.border} p-4 mb-3 hover:shadow-lg transition-all`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Animated Platform Icon */}
          <motion.div
            whileHover={{ scale: 1.2, rotate: 10 }}
            className={`text-3xl bg-gradient-to-r ${config.gradient} p-3 rounded-xl shadow-md`}
          >
            {config.emoji}
          </motion.div>

          {/* Platform Details */}
          <div>
            <p className="font-semibold text-slate-900">{platform}</p>
            <p className={`text-sm ${cfg.text} font-medium`}>{cfg.icon} {status}</p>
          </div>
        </div>

        {/* Amount with animation */}
        <motion.div
          initial={{ scale: 0.8 }}
          animate={{ scale: 1 }}
          transition={{ delay: delay + 0.2 }}
          className="text-right"
        >
          <p className="text-2xl font-bold text-slate-900">₹{Number(amount).toFixed(2)}</p>
          <p className="text-xs text-slate-500">Transaction</p>
        </motion.div>
      </div>
    </motion.div>
  )
}

const AnimatedTransactionCard = ({ transaction, delay = 0 }) => {
  const { txn_type, amount, method, status, gateway_ref, created_at, user_platform } = transaction
  const platform = user_platform || 'Other'
  const config = PLATFORM_CONFIGS[platform] || PLATFORM_CONFIGS['Other']

  const statusColors = {
    Success: { bg: 'from-green-400 to-emerald-500', text: 'text-green-600', badge: 'bg-green-100' },
    Failed: { bg: 'from-red-400 to-rose-500', text: 'text-red-600', badge: 'bg-red-100' },
    Pending: { bg: 'from-yellow-400 to-amber-500', text: 'text-yellow-600', badge: 'bg-yellow-100' }
  }

  const sColors = statusColors[status] || statusColors['Pending']

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      whileHover={{ scale: 1.02, translateY: -4 }}
      className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-4 hover:bg-white/10 transition-all"
    >
      <div className="flex items-start justify-between gap-4">
        {/* Left: Platform badge and details */}
        <div className="flex gap-3 flex-1">
          <motion.div
            whileHover={{ rotate: 360, scale: 1.1 }}
            transition={{ duration: 0.6 }}
            className={`bg-gradient-to-r ${config.gradient} p-2.5 rounded-lg text-xl shadow-md flex-shrink-0`}
          >
            {config.emoji}
          </motion.div>

          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-white capitalize">{txn_type}</h3>
              <motion.span
                animate={{ scale: [1, 1.1, 1] }}
                transition={{ repeat: Infinity, duration: 2 }}
                className={`${sColors.badge} px-2 py-0.5 rounded-full text-xs font-bold ${sColors.text}`}
              >
                {status}
              </motion.span>
            </div>
            <p className="text-xs text-white/60 mt-0.5">via {method} • {platform}</p>
            {gateway_ref && (
              <p className="text-xs text-white/50 mt-1 font-mono">Ref: {gateway_ref.slice(0, 20)}...</p>
            )}
          </div>
        </div>

        {/* Right: Amount and date */}
        <div className="text-right flex-shrink-0">
          <motion.p
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            transition={{ delay: delay + 0.2 }}
            className={`text-xl font-bold bg-gradient-to-r ${sColors.bg} bg-clip-text text-transparent`}
          >
            ₹{Number(amount).toFixed(2)}
          </motion.p>
          <p className="text-xs text-white/60 mt-0.5">{created_at?.slice(0, 10)}</p>
        </div>
      </div>

      {/* Progress bar animation */}
      <motion.div
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ delay: delay + 0.3 }}
        className={`mt-3 h-1 bg-gradient-to-r ${sColors.bg} rounded-full origin-left`}
      />
    </motion.div>
  )
}

export { AnimatedPlatformLogo, AnimatedTransactionCard, PLATFORM_CONFIGS }