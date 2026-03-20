import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import heroImage from '../assets/rider-hero.svg'

export default function HomePage() {
  return (
    <div className="relative overflow-hidden px-6 pb-20 pt-16 sm:px-10">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="blob-left" />
        <div className="blob-right" />
      </div>

      {/* Hero */}
      <section className="mx-auto grid max-w-6xl items-center gap-10 lg:grid-cols-2">
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
          <p className="mb-3 inline-flex rounded-full bg-white/70 px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700">
            Income Protection for Delivery Workers
          </p>
          <h1 className="font-outfit text-4xl font-bold leading-tight text-slate-800 sm:text-6xl">
            Protect Your Gig Income From Weather Disruptions
          </h1>
          <p className="mt-5 max-w-xl text-lg text-slate-700">
            Delivery workers lose income during heavy rain. GigCover AI automatically protects their income using
            parametric risk intelligence and instant claim triggers.
          </p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link to="/signup" className="primary-btn text-base">
              🚀 Get Covered Now
            </Link>
            <Link to="/login" className="secondary-btn text-base">
              Login
            </Link>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.1 }}
          className="glass rounded-3xl p-8"
        >
          <h2 className="font-space text-2xl font-semibold text-slate-800">Gig Worker Safety, Simplified</h2>
          <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <img src={heroImage} alt="GigCover worker" className="h-72 w-full object-contain" />
          </div>
          <div className="mt-5 rounded-2xl bg-white/80 p-4 text-sm text-slate-700">
            Real-time weather risk, automated premium updates, and instant claim eligibility in one mobile-first system.
          </div>
        </motion.div>
      </section>

    </div>
  )
}
