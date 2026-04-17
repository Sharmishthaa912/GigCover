import { motion } from 'framer-motion'

const GlassCard = ({ children, className = '', delay = 0 }) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay }}
      className={`backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 ${className}`}
    >
      {children}
    </motion.div>
  )
}

export default GlassCard