import { motion } from 'framer-motion'

const AnimatedButton = ({
  children,
  variant = 'primary',
  className = '',
  onClick,
  disabled = false,
  ...props
}) => {
  const baseClasses = 'px-6 py-3 rounded-xl font-semibold transition-all duration-200 relative overflow-hidden'

  const variants = {
    primary: 'bg-gradient-to-r from-blue-500 to-purple-600 text-white hover:from-blue-600 hover:to-purple-700 shadow-lg hover:shadow-xl',
    secondary: 'bg-white/10 text-white border border-white/20 hover:bg-white/20 backdrop-blur-sm',
    outline: 'border-2 border-white/30 text-white hover:bg-white/10 backdrop-blur-sm'
  }

  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      disabled={disabled}
      className={`${baseClasses} ${variants[variant]} ${className} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      {...props}
    >
      {/* Ripple effect */}
      <motion.span
        className="absolute inset-0 bg-white/20 rounded-xl"
        initial={{ scale: 0, opacity: 1 }}
        whileTap={{ scale: 4, opacity: 0 }}
        transition={{ duration: 0.3 }}
      />
      <span className="relative z-10">{children}</span>
    </motion.button>
  )
}

export default AnimatedButton