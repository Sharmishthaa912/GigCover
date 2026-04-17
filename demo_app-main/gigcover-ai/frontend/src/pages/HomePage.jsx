import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import AnimatedButton from '../components/ui/AnimatedButton'
import GlassCard from '../components/ui/GlassCard'

export default function HomePage() {
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.2,
        delayChildren: 0.1
      }
    }
  }

  const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6, ease: "easeOut" }
    }
  }

  const floatingVariants = {
    animate: {
      y: [-10, 10, -10],
      transition: {
        duration: 6,
        repeat: Infinity,
        ease: "easeInOut"
      }
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden">
      {/* Animated Background */}
      <div className="absolute inset-0 bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900">
        <motion.div
          animate={{
            backgroundPosition: ['0% 0%', '100% 100%'],
          }}
          transition={{
            duration: 20,
            repeat: Infinity,
            repeatType: "reverse",
            ease: "linear"
          }}
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage: 'radial-gradient(circle at 20% 50%, rgba(120, 119, 198, 0.3), transparent 50%), radial-gradient(circle at 80% 20%, rgba(255, 119, 198, 0.3), transparent 50%), radial-gradient(circle at 40% 80%, rgba(120, 219, 255, 0.3), transparent 50%)',
            backgroundSize: '100% 100%'
          }}
        />
      </div>

      {/* Floating Elements */}
      <motion.div
        variants={floatingVariants}
        animate="animate"
        className="absolute top-20 left-10 w-20 h-20 bg-purple-500/20 rounded-full blur-xl"
      />
      <motion.div
        variants={floatingVariants}
        animate="animate"
        className="absolute top-40 right-20 w-32 h-32 bg-blue-500/20 rounded-full blur-xl"
        style={{ animationDelay: '2s' }}
      />
      <motion.div
        variants={floatingVariants}
        animate="animate"
        className="absolute bottom-20 left-1/4 w-24 h-24 bg-pink-500/20 rounded-full blur-xl"
        style={{ animationDelay: '4s' }}
      />

      <div className="relative z-10 px-6 pb-20 pt-16 sm:px-10">
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="mx-auto max-w-7xl"
        >
          {/* Hero Section */}
          <motion.section
            variants={itemVariants}
            className="text-center mb-20"
          >
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="inline-flex items-center px-4 py-2 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 text-white/90 text-sm font-medium mb-8"
            >
              <span className="w-2 h-2 bg-green-400 rounded-full mr-2 animate-pulse"></span>
              Income Protection for Delivery Workers
            </motion.div>

            <motion.h1
              variants={itemVariants}
              className="text-5xl md:text-7xl font-bold text-white mb-6 leading-tight"
            >
              Protecting Gig Workers
              <motion.span
                animate={{
                  backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'],
                }}
                transition={{
                  duration: 5,
                  repeat: Infinity,
                  ease: "linear"
                }}
                className="bg-gradient-to-r from-purple-400 via-pink-400 to-blue-400 bg-clip-text text-transparent"
              >
                {" "}Income{" "}
              </motion.span>
              in Real-Time
            </motion.h1>

            <motion.p
              variants={itemVariants}
              className="text-xl text-white/80 max-w-3xl mx-auto mb-10 leading-relaxed"
            >
              Delivery workers lose income during heavy rain. GigCover AI automatically protects their income using
              parametric risk intelligence and instant claim triggers.
            </motion.p>

            <motion.div
              variants={itemVariants}
              className="flex flex-col sm:flex-row gap-4 justify-center"
            >
              <Link to="/signup">
                <AnimatedButton className="px-8 py-4 text-lg font-semibold">
                  🚀 Get Covered Now
                </AnimatedButton>
              </Link>
              <Link to="/login">
                <AnimatedButton variant="secondary" className="px-8 py-4 text-lg font-semibold">
                  Login to Dashboard
                </AnimatedButton>
              </Link>
            </motion.div>
          </motion.section>

          {/* Features Grid */}
          <motion.div
            variants={containerVariants}
            className="grid md:grid-cols-3 gap-8 mb-20"
          >
            <GlassCard delay={0.3}>
              <div className="text-center p-8">
                <motion.div
                  whileHover={{ scale: 1.1, rotate: 5 }}
                  className="w-16 h-16 bg-gradient-to-r from-purple-500 to-blue-500 rounded-2xl flex items-center justify-center mx-auto mb-6"
                >
                  <span className="text-2xl">🌧️</span>
                </motion.div>
                <h3 className="text-xl font-bold text-white mb-4">Weather Intelligence</h3>
                <p className="text-white/70">
                  Real-time weather monitoring with AI-powered risk assessment for instant protection activation.
                </p>
              </div>
            </GlassCard>

            <GlassCard delay={0.5}>
              <div className="text-center p-8">
                <motion.div
                  whileHover={{ scale: 1.1, rotate: 5 }}
                  className="w-16 h-16 bg-gradient-to-r from-green-500 to-teal-500 rounded-2xl flex items-center justify-center mx-auto mb-6"
                >
                  <span className="text-2xl">⚡</span>
                </motion.div>
                <h3 className="text-xl font-bold text-white mb-4">Instant Claims</h3>
                <p className="text-white/70">
                  Zero-touch claim processing with automated payout triggers when weather conditions breach thresholds.
                </p>
              </div>
            </GlassCard>

            <GlassCard delay={0.7}>
              <div className="text-center p-8">
                <motion.div
                  whileHover={{ scale: 1.1, rotate: 5 }}
                  className="w-16 h-16 bg-gradient-to-r from-orange-500 to-red-500 rounded-2xl flex items-center justify-center mx-auto mb-6"
                >
                  <span className="text-2xl">🛡️</span>
                </motion.div>
                <h3 className="text-xl font-bold text-white mb-4">Fraud Protection</h3>
                <p className="text-white/70">
                  Advanced ML algorithms detect fraudulent claims while ensuring genuine claims are processed instantly.
                </p>
              </div>
            </GlassCard>
          </motion.div>

          {/* Stats Section */}
          <motion.div
            variants={itemVariants}
            className="text-center"
          >
            <GlassCard className="max-w-4xl mx-auto">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-8 p-8">
                <div>
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 1, duration: 0.5 }}
                    className="text-3xl font-bold text-white mb-2"
                  >
                    10K+
                  </motion.div>
                  <div className="text-white/60">Workers Protected</div>
                </div>
                <div>
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 1.2, duration: 0.5 }}
                    className="text-3xl font-bold text-white mb-2"
                  >
                    ₹2.5Cr
                  </motion.div>
                  <div className="text-white/60">Claims Paid</div>
                </div>
                <div>
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 1.4, duration: 0.5 }}
                    className="text-3xl font-bold text-white mb-2"
                  >
                    99.9%
                  </motion.div>
                  <div className="text-white/60">Uptime</div>
                </div>
                <div>
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 1.6, duration: 0.5 }}
                    className="text-3xl font-bold text-white mb-2"
                  >
                    &lt;30s
                  </motion.div>
                  <div className="text-white/60">Claim Processing</div>
                </div>
              </div>
            </GlassCard>
          </motion.div>
        </motion.div>
      </div>
    </div>
  )
}
